# PDE Lecture Notes: Elliptic and Parabolic Equations

## Chapter 1: Second-Order Elliptic PDEs

### Definition 1.1 (Elliptic Operator)
A second-order linear partial differential operator

$$
Lu = \sum_{i,j=1}^n a^{ij}(x) \partial_i \partial_j u + \sum_{i=1}^n b^i(x) \partial_i u + c(x) u
$$

is called **uniformly elliptic** if there exists $\lambda > 0$ such that

$$
\sum_{i,j} a^{ij}(x) \xi_i \xi_j \geq \lambda |\xi|^2
$$

for all $x \in \Omega$ and $\xi \in \mathbb{R}^n$.

### Theorem 1.2 (Maximum Principle for Elliptic Operators)
Let $Lu \geq 0$ in a bounded domain $\Omega$ with $c \leq 0$.  Then:

$$
\sup_\Omega u \leq \sup_{\partial \Omega} u^+
$$

### Proof
Suppose $u$ attains a positive interior maximum at $x_0 \in \Omega$.  At $x_0$:
- $\nabla u(x_0) = 0$
- The Hessian $D^2 u(x_0)$ is negative semi-definite

Therefore $\sum a^{ij} \partial_i \partial_j u(x_0) \leq 0$ and $\sum b^i \partial_i u(x_0) = 0$,
giving $Lu(x_0) \leq c(x_0) u(x_0) \leq 0$, a contradiction.  $\square$

### Example 1.3
The Laplacian $\Delta = \sum \partial_i^2$ is uniformly elliptic with $\lambda = 1$.
The maximum principle for harmonic functions ($\Delta u = 0$) is the special case $a^{ij} = \delta^{ij}$,
$b^i = 0$, $c = 0$.

---

## Chapter 2: The Dirichlet Problem

### Theorem 2.1 (Existence and Uniqueness)
For a bounded domain $\Omega$ with smooth boundary, the Dirichlet problem

$$
\begin{cases}
\Delta u = f & \text{in } \Omega \\
u = \phi & \text{on } \partial \Omega
\end{cases}
$$

has a unique solution $u \in C^2(\Omega) \cap C^0(\overline{\Omega})$ for any $f \in C^0(\Omega)$
and $\phi \in C^0(\partial \Omega)$.

### Proof sketch
Existence follows from the method of sub- and supersolutions or from Perron's method.
Uniqueness follows immediately from the maximum principle. $\square$

### Remark 2.2
The solution can be written using the Green's function:

$$
u(x) = \int_{\partial \Omega} \phi(y) \frac{\partial G}{\partial \nu}(x, y) \, dS(y)
- \int_\Omega f(y) G(x, y) \, dy
$$

---

## Chapter 3: Parabolic Equations and the Heat Equation

### Definition 3.1 (Heat Equation)
The heat equation on $\mathbb{R}^n \times (0, T)$ is:

$$
\partial_t u = \Delta u
$$

The fundamental solution (heat kernel) is:

$$
K(x, y, t) = \frac{1}{(4\pi t)^{n/2}} \exp\!\left( -\frac{|x-y|^2}{4t} \right)
$$

### Theorem 3.2 (Maximum Principle for the Heat Equation)
If $u \in C^{2,1}(\Omega_T) \cap C^0(\overline{\Omega_T})$ satisfies $\partial_t u - \Delta u \leq 0$
in $\Omega_T = \Omega \times (0, T]$, then:

$$
\max_{\overline{\Omega_T}} u = \max_{\partial_p \Omega_T} u
$$

where $\partial_p \Omega_T = (\partial \Omega \times [0,T]) \cup (\Omega \times \{0\})$ is the parabolic boundary.

### Corollary 3.3
Solutions of the heat equation are smooth for $t > 0$ (parabolic regularity).

---

## Chapter 4: Harnack Inequalities

### Theorem 4.1 (Elliptic Harnack Inequality)
Let $u > 0$ be a harmonic function in $B(x_0, R)$.  Then:

$$
\sup_{B(x_0, R/2)} u \leq C(n) \inf_{B(x_0, R/2)} u
$$

### Theorem 4.2 (Li-Yau Parabolic Harnack)
Let $(M, g)$ be a complete Riemannian manifold with $\operatorname{Ric} \geq 0$.
If $u > 0$ solves $\partial_t u = \Delta u$, then for $0 < t_1 < t_2$:

$$
u(x_1, t_1) \leq u(x_2, t_2) \left( \frac{t_2}{t_1} \right)^{n/2}
\exp\!\left( \frac{d(x_1, x_2)^2}{4(t_2 - t_1)} \right)
$$

### Proof sketch
Applying the gradient estimate to $f = \log u$:

$$
\partial_t f - |\nabla f|^2 - \frac{n}{2t} \geq 0
$$

Integrating along the space-time geodesic from $(x_1, t_1)$ to $(x_2, t_2)$
yields the Harnack inequality. $\square$

---

## Chapter 5: Sobolev Spaces and Elliptic Regularity

### Definition 5.1 (Sobolev Space)
For $k \in \mathbb{N}$ and $p \geq 1$, the Sobolev space $W^{k,p}(\Omega)$ consists of
functions $u \in L^p(\Omega)$ whose distributional derivatives $D^\alpha u$ of order $|\alpha| \leq k$
belong to $L^p(\Omega)$, with norm:

$$
\| u \|_{W^{k,p}} = \left( \sum_{|\alpha| \leq k} \| D^\alpha u \|_{L^p}^p \right)^{1/p}
$$

### Theorem 5.2 (Sobolev Embedding)
For $\Omega \subset \mathbb{R}^n$ bounded with Lipschitz boundary:
- If $kp < n$: $W^{k,p}(\Omega) \hookrightarrow L^{np/(n-kp)}(\Omega)$
- If $kp = n$: $W^{k,p}(\Omega) \hookrightarrow L^q(\Omega)$ for all $q < \infty$
- If $kp > n$: $W^{k,p}(\Omega) \hookrightarrow C^{0,\alpha}(\Omega)$ with $\alpha = k - n/p$

### Theorem 5.3 (Elliptic Regularity)
If $Lu = f$ with $L$ uniformly elliptic, $f \in L^p(\Omega)$, and $u \in W^{1,p}(\Omega)$,
then $u \in W^{2,p}_{\mathrm{loc}}(\Omega)$ and:

$$
\| u \|_{W^{2,p}(B_{r/2})} \leq C \left( \| u \|_{L^p(B_r)} + \| f \|_{L^p(B_r)} \right)
$$
