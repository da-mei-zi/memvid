//! Command-line interface for Memvid operations.
//!
//! Provides JSON-based subcommands for creating, writing to, searching, and
//! inspecting `.mv2` memory files.  All output is written to stdout as
//! newline-terminated JSON so that external programs (e.g., Python scripts)
//! can parse results without additional tooling.
//!
//! # Subcommands
//!
//! ```text
//! memvid-cli create  <path>
//! memvid-cli put     <path>   (reads a JSON document descriptor from stdin)
//! memvid-cli commit  <path>
//! memvid-cli search  <path>  <query>  [--top-k N]  [--snippet-chars N]
//! memvid-cli stats   <path>
//! ```
//!
//! # Put JSON schema (stdin)
//!
//! ```json
//! {
//!   "text": "...",
//!   "title": "optional title",
//!   "uri":   "optional uri",
//!   "extra_metadata": {
//!     "doc_id": "D001",
//!     "page":   "12",
//!     "subject": "Riemannian Geometry",
//!     "topic":   "Bochner formula",
//!     "difficulty": "advanced",
//!     "source_type": "pdf"
//!   }
//! }
//! ```

use std::collections::BTreeMap;
use std::env;
use std::io::{self, Read};
use std::path::PathBuf;
use std::process;

use memvid_core::{Memvid, PutOptions, SearchRequest};
use memvid_core::types::AclEnforcementMode;
use serde::{Deserialize, Serialize};
use serde_json::Value;

// ---------------------------------------------------------------------------
// Input / output types
// ---------------------------------------------------------------------------

/// Input document supplied via stdin for the `put` subcommand.
#[derive(Debug, Deserialize)]
struct PutInput {
    text: String,
    #[serde(default)]
    title: Option<String>,
    #[serde(default)]
    uri: Option<String>,
    #[serde(default)]
    extra_metadata: BTreeMap<String, String>,
}

/// Minimal serialisable representation of a search hit for JSON output.
#[derive(Debug, Serialize)]
struct HitOut {
    rank: usize,
    frame_id: u64,
    uri: String,
    title: Option<String>,
    text: String,
    score: Option<f32>,
    extra_metadata: BTreeMap<String, String>,
}

/// JSON output for the `search` subcommand.
#[derive(Debug, Serialize)]
struct SearchOut {
    query: String,
    top_k: usize,
    total_hits: usize,
    elapsed_ms: u128,
    engine: String,
    hits: Vec<HitOut>,
}

/// JSON output for the `put` subcommand.
#[derive(Debug, Serialize)]
struct PutOut {
    seq: u64,
}

/// JSON output for the `commit` subcommand.
#[derive(Debug, Serialize)]
struct CommitOut {
    ok: bool,
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn print_json<T: Serialize>(value: &T) {
    match serde_json::to_string(value) {
        Ok(s) => println!("{s}"),
        Err(e) => {
            eprintln!("JSON serialisation error: {e}");
            process::exit(1);
        }
    }
}

fn usage() -> ! {
    eprintln!(
        "Usage:
  memvid-cli create <path>
  memvid-cli put    <path>                        (JSON document on stdin)
  memvid-cli commit <path>
  memvid-cli search <path> <query> [--top-k N] [--snippet-chars N]
  memvid-cli stats  <path>
"
    );
    process::exit(1);
}

fn require_path(args: &[String], index: usize) -> PathBuf {
    args.get(index)
        .map(PathBuf::from)
        .unwrap_or_else(|| usage())
}

// ---------------------------------------------------------------------------
// Subcommand implementations
// ---------------------------------------------------------------------------

fn cmd_create(path: PathBuf) {
    match Memvid::create(&path) {
        Ok(_) => print_json(&serde_json::json!({ "ok": true, "path": path.display().to_string() })),
        Err(e) => {
            eprintln!("create error: {e}");
            process::exit(1);
        }
    }
}

fn cmd_put(path: PathBuf) {
    // Read JSON document from stdin.
    let mut stdin_buf = String::new();
    io::stdin()
        .read_to_string(&mut stdin_buf)
        .unwrap_or_else(|e| {
            eprintln!("stdin read error: {e}");
            process::exit(1);
        });

    let input: PutInput = serde_json::from_str(&stdin_buf).unwrap_or_else(|e| {
        eprintln!("JSON parse error: {e}");
        process::exit(1);
    });

    let mut mem = Memvid::open(&path).unwrap_or_else(|e| {
        eprintln!("open error: {e}");
        process::exit(1);
    });

    let mut builder = PutOptions::builder();
    if let Some(t) = &input.title {
        builder = builder.title(t.as_str());
    }
    if let Some(u) = &input.uri {
        builder = builder.uri(u.as_str());
    }
    for (k, v) in &input.extra_metadata {
        builder = builder.tag(k.as_str(), v.as_str());
    }
    let options = builder.build();

    let seq = mem
        .put_bytes_with_options(input.text.as_bytes(), options)
        .unwrap_or_else(|e| {
            eprintln!("put error: {e}");
            process::exit(1);
        });

    mem.commit().unwrap_or_else(|e| {
        eprintln!("auto-commit error: {e}");
        process::exit(1);
    });

    print_json(&PutOut { seq });
}

fn cmd_commit(path: PathBuf) {
    let mut mem = Memvid::open(&path).unwrap_or_else(|e| {
        eprintln!("open error: {e}");
        process::exit(1);
    });

    mem.commit().unwrap_or_else(|e| {
        eprintln!("commit error: {e}");
        process::exit(1);
    });

    print_json(&CommitOut { ok: true });
}

fn cmd_search(path: PathBuf, args: &[String]) {
    // args is the slice starting right after "search <path>":
    // args[0] = query
    // remaining pairs: --top-k N  --snippet-chars N
    let query = args.first().cloned().unwrap_or_else(|| {
        eprintln!("search requires a query argument");
        usage()
    });

    let mut top_k: usize = 5;
    let mut snippet_chars: usize = 300;

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--top-k" | "-k" => {
                i += 1;
                top_k = args.get(i).and_then(|s| s.parse().ok()).unwrap_or(top_k);
            }
            "--snippet-chars" | "-s" => {
                i += 1;
                snippet_chars = args
                    .get(i)
                    .and_then(|s| s.parse().ok())
                    .unwrap_or(snippet_chars);
            }
            _ => {}
        }
        i += 1;
    }

    let mut mem = Memvid::open(&path).unwrap_or_else(|e| {
        eprintln!("open error: {e}");
        process::exit(1);
    });

    let request = SearchRequest {
        query: query.clone(),
        top_k,
        snippet_chars,
        uri: None,
        scope: None,
        cursor: None,
        as_of_frame: None,
        as_of_ts: None,
        no_sketch: false,
        acl_context: None,
        acl_enforcement_mode: AclEnforcementMode::Audit,
    };

    let response = mem.search(request).unwrap_or_else(|e| {
        eprintln!("search error: {e}");
        process::exit(1);
    });

    let hits: Vec<HitOut> = response
        .hits
        .into_iter()
        .map(|h| HitOut {
            rank: h.rank,
            frame_id: h.frame_id,
            uri: h.uri,
            title: h.title,
            text: h.text,
            score: h.score,
            extra_metadata: h
                .metadata
                .map(|m| m.extra_metadata)
                .unwrap_or_default(),
        })
        .collect();

    let engine_str = format!("{:?}", response.engine);

    print_json(&SearchOut {
        query,
        top_k,
        total_hits: response.total_hits,
        elapsed_ms: response.elapsed_ms,
        engine: engine_str,
        hits,
    });
}

fn cmd_stats(path: PathBuf) {
    let mem = Memvid::open(&path).unwrap_or_else(|e| {
        eprintln!("open error: {e}");
        process::exit(1);
    });

    let stats = mem.stats().unwrap_or_else(|e| {
        eprintln!("stats error: {e}");
        process::exit(1);
    });

    // Re-serialise via serde_json so all fields are included.
    let v: Value = serde_json::to_value(&stats).unwrap_or_else(|e| {
        eprintln!("stats serialisation error: {e}");
        process::exit(1);
    });
    println!("{v}");
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

fn main() {
    let args: Vec<String> = env::args().collect();

    // args[0] = binary name
    let subcommand = args.get(1).map(String::as_str).unwrap_or_else(|| usage());

    match subcommand {
        "create" => {
            let path = require_path(&args, 2);
            cmd_create(path);
        }
        "put" => {
            let path = require_path(&args, 2);
            cmd_put(path);
        }
        "commit" => {
            let path = require_path(&args, 2);
            cmd_commit(path);
        }
        "search" => {
            let path = require_path(&args, 2);
            // remaining args start at index 3
            cmd_search(path, &args[3..]);
        }
        "stats" => {
            let path = require_path(&args, 2);
            cmd_stats(path);
        }
        _ => usage(),
    }
}
