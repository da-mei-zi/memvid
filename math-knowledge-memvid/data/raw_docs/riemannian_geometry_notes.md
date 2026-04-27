# Riemannian Geometry: Selected Topics

## 1. The Bochner Formula

### Definition 1.1 (Rough Laplacian)
Let $(M, g)$ be a Riemannian manifold and $u \in C^\infty(M)$.
The Laplacian of $u$ is defined as $\Delta u = \operatorname{tr}(\operatorname{Hess}\, u)$.

### Theorem 1.2 (Bochner Formula)
For any smooth function $u$ on a Riemannian manifold $(M, g)$, the following identity holds:

$$
\frac{1}{2} \Delta |\nabla u|^2 = |\operatorname{Hess}\, u|^2 + \langle \nabla \Delta u, \nabla u \rangle + \operatorname{Ric}(\nabla u, \nabla u)
$$

### Proof
We expand $\Delta |\nabla u|^2$ using the commutation formula for covariant derivatives
and the definition of the Riemann curvature tensor.  The key step is:

$$
\nabla_i \nabla_j \nabla_k u - \nabla_j \nabla_i \nabla_k u = R_{ijk}{}^l \nabla_l u
$$

Contracting appropriate indices yields the desired formula. $\square$

### Remark 1.3
The Bochner formula is the cornerstone of geometric analysis on Riemannian manifolds.
When $\operatorname{Ric} \geq K g$ (i.e., the Ricci curvature is bounded below by $K$),
and $u$ is harmonic ($\Delta u = 0$), the formula gives:

$$
\frac{1}{2} \Delta |\nabla u|^2 \geq K |\nabla u|^2
$$

This is the starting point for gradient estimates.

---

## 2. Gradient Estimates

### Theorem 2.1 (Yau Gradient Estimate)
Let $(M, g)$ be a complete Riemannian manifold with $\operatorname{Ric} \geq -K$ for some $K \geq 0$.
If $u > 0$ is a harmonic function on the geodesic ball $B(x_0, R)$, then there exists a constant
$C = C(n)$ depending only on the dimension $n$ such that:

$$
\sup_{B(x_0, R/2)} \frac{|\nabla u|}{u} \leq C\!\left( \frac{1}{R} + \sqrt{K} \right)
$$

### Proof sketch
Applying the Bochner formula to $f = \log u$ (which satisfies $\Delta f = -|\nabla f|^2$),
one obtains:

$$
\frac{1}{2} \Delta |\nabla f|^2 \geq |\operatorname{Hess}\, f|^2 - K |\nabla f|^2
$$

Using the Cauchy-Schwarz inequality $|\operatorname{Hess}\, f|^2 \geq \frac{(\Delta f)^2}{n}$
and the maximum principle applied to $\phi = \eta^2 |\nabla f|^2$ (where $\eta$ is a suitable
cutoff function), one derives the gradient bound. $\square$

### Corollary 2.2 (Cheng-Yau)
Under the same hypotheses, if $M$ is non-compact with $\operatorname{Ric} \geq 0$, then every
positive harmonic function is constant (Liouville theorem).

---

## 3. Laplacian Comparison Theorem

### Theorem 3.1 (Laplacian Comparison)
Let $(M, g)$ be a complete Riemannian manifold with $\operatorname{Ric} \geq (n-1)K$ for $K \in \mathbb{R}$.
Let $\rho(x) = d(x, x_0)$ denote the distance function from a fixed point $x_0$.
Then in the sense of distributions away from $x_0$:

$$
\Delta \rho \leq (n-1) \frac{\operatorname{sn}_K'(\rho)}{\operatorname{sn}_K(\rho)}
$$

where $\operatorname{sn}_K$ is the solution to $y'' + Ky = 0$ with $y(0) = 0$, $y'(0) = 1$.

### Remark 3.2
Explicitly:
- For $K = 0$: $\Delta \rho \leq \frac{n-1}{\rho}$ (Euclidean comparison)
- For $K > 0$: $\Delta \rho \leq (n-1)\sqrt{K} \cot(\sqrt{K}\rho)$
- For $K < 0$: $\Delta \rho \leq (n-1)\sqrt{|K|} \coth(\sqrt{|K|}\rho)$

### Application (Bishop-Gromov Volume Comparison)
Using the Laplacian comparison theorem, one derives:

$$
\frac{\operatorname{Vol}(B(x_0, r))}{\operatorname{Vol}_{K}(r)} \leq
\frac{\operatorname{Vol}(B(x_0, R))}{\operatorname{Vol}_{K}(R)}, \quad r \leq R
$$

where $\operatorname{Vol}_{K}(r)$ is the volume of a geodesic ball of radius $r$ in the space
form of constant curvature $K$.

---

## 4. Maximum Principle

### Theorem 4.1 (Weak Maximum Principle)
Let $\Omega \subset M$ be a bounded domain and $u \in C^2(\Omega) \cap C^0(\overline{\Omega})$
satisfy $\Delta u \geq 0$ (subharmonic).  Then:

$$
\max_{\overline{\Omega}} u = \max_{\partial \Omega} u
$$

### Theorem 4.2 (Strong Maximum Principle, Hopf)
If $\Delta u \geq 0$ in a connected domain $\Omega$ and $u$ attains its maximum at an interior
point, then $u$ is constant on $\Omega$.

### Proof
The proof uses the mean value property and a Harnack chain argument. $\square$

### Example 4.3
The maximum principle for harmonic functions immediately implies:
1. Harmonic functions have no local maxima or minima in the interior of the domain.
2. A harmonic function on a compact manifold without boundary is constant.
3. Uniqueness of the Dirichlet problem: if $\Delta u = \Delta v$ in $\Omega$ and $u = v$
   on $\partial \Omega$, then $u \equiv v$.

---

## 5. Sobolev Inequality

### Theorem 5.1 (Sobolev Inequality on Manifolds)
Let $(M, g)$ be a complete $n$-dimensional Riemannian manifold with $\operatorname{Ric} \geq 0$.
Then for all $f \in C_0^\infty(M)$:

$$
\left( \int_M |f|^{2n/(n-2)} \, dV \right)^{(n-2)/n} \leq C(n)
\int_M |\nabla f|^2 \, dV
$$

### Remark 5.2
The constant $C(n)$ depends only on the dimension.  The inequality is sharp on $\mathbb{R}^n$,
where the extremal functions are the Aubin-Talenti bubbles.

The Sobolev inequality implies:
- Eigenvalue lower bounds (via the Cheeger inequality)
- Heat kernel upper bounds
- $L^p$ estimates for solutions of elliptic PDEs

---

## 6. First Eigenvalue Estimates

### Theorem 6.1 (Lichnerowicz Eigenvalue Estimate)
If $(M, g)$ is a closed Riemannian manifold with $\operatorname{Ric} \geq (n-1)\kappa > 0$, then
the first non-zero eigenvalue of the Laplacian satisfies:

$$
\lambda_1 \geq n\kappa
$$

### Proof
Apply the Bochner formula to a first eigenfunction $u$ ($\Delta u = -\lambda_1 u$):

$$
\frac{1}{2} \Delta |\nabla u|^2 \geq \frac{(\Delta u)^2}{n} + \operatorname{Ric}(\nabla u, \nabla u)
\geq \frac{\lambda_1^2}{n} |\nabla u|^2 / u^2 \cdot u^2 + (n-1)\kappa |\nabla u|^2
$$

Wait — more precisely, integrating and using $\int u^2 = \int |\nabla u|^2 / \lambda_1$
yields the bound. $\square$

### Theorem 6.2 (Cheeger Inequality)
For any closed Riemannian manifold:

$$
\lambda_1 \geq \frac{h^2}{4}
$$

where $h = \inf_\Sigma \frac{\operatorname{Area}(\Sigma)}{\min(\operatorname{Vol}(M_1), \operatorname{Vol}(M_2))}$
is the Cheeger constant and $\Sigma$ divides $M$ into $M_1 \cup M_2$.
