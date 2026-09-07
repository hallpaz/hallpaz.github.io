---
title: "A Geometric Primer on Neural Implicit Representations: From Signed Distance Fields to Manifold Learning"
author: "Hallison Paz"
date: 2024-06-20
tags: ["Computer Vision", "Differential Geometry", "Neural Implicit", "PyTorch"]
summary: "An introduction to coordinate-based neural representations, continuous level sets, and how enforcing the Eikonal equation allows deep networks to parameterize smooth 3D surfaces."
lang: "en"
draft: true
---

Traditional 3D computer graphics represents shapes using discrete primitives: polygon meshes, voxel grids, or point clouds. While effective for rasterization, these discrete representations struggle with continuous topological changes, infinite resolution, and differentiable optimization.

**Neural Implicit Representations** parameterize 3D geometry as continuous coordinate networks: a Multi-Layer Perceptron (MLP) mapping spatial coordinates $\mathbf{x} \in \mathbb{R}^3$ directly to geometric quantities such as occupancy or signed distance.

---

## Signed Distance Functions (SDF)

A **Signed Distance Function** $f: \Omega \subset \mathbb{R}^3 \to \mathbb{R}$ of a closed domain $\Omega$ with boundary $\partial \Omega$ assigns to each spatial point $\mathbf{x}$ the shortest Euclidean distance to $\partial \Omega$, with a sign denoting interior versus exterior:

$$f(\mathbf{x}) = \begin{cases} -d(\mathbf{x}, \partial \Omega) & \text{if } \mathbf{x} \in \mathrm{int}(\Omega) \\ 0 & \text{if } \mathbf{x} \in \partial \Omega \\ +d(\mathbf{x}, \partial \Omega) & \text{if } \mathbf{x} \in \mathrm{ext}(\Omega) \end{cases}$$

The surface of interest $\mathcal{M}$ is precisely the **zero-level set** of $f$:

$$\mathcal{M} = \{\mathbf{x} \in \mathbb{R}^3 : f(\mathbf{x}) = 0\}$$

---

## The Differential Geometry: Normal Vectors & The Eikonal Equation

Because $f$ is continuous, we can analyze its differential properties using calculus on manifolds. By the implicit function theorem, if $\nabla f(\mathbf{x}) \neq \mathbf{0}$, the unit surface normal $\mathbf{n}(\mathbf{x})$ to the level set at $\mathbf{x}$ is simply the normalized spatial gradient:

$$\mathbf{n}(\mathbf{x}) = \frac{\nabla_{\mathbf{x}} f(\mathbf{x})}{\|\nabla_{\mathbf{x}} f(\mathbf{x})\|}$$

Furthermore, a valid signed distance field must satisfy the **Eikonal equation** almost everywhere:

$$\|\nabla_{\mathbf{x}} f(\mathbf{x})\|_2 = 1 \quad \text{a.e.}$$

This property states that the magnitude of the gradient of distance is identically unity—the field varies at a constant rate of 1 meter per meter traveled in the steepest ascent direction.

When training a neural network $f_{\boldsymbol{\theta}}(\mathbf{x})$ to represent geometry, we enforce this geometric prior using an **Eikonal regularization loss**:

$$\mathcal{L}_{\mathrm{eikonal}}(\boldsymbol{\theta}) = \mathbb{E}_{\mathbf{x} \sim \Omega} \left[ \left( \|\nabla_{\mathbf{x}} f_{\boldsymbol{\theta}}(\mathbf{x})\|_2 - 1 \right)^2 \right]$$

---

## Implementing Coordinate Networks & Eikonal Regularization

Below is a complete PyTorch implementation demonstrating how to query a coordinate network, compute exact gradients with automatic differentiation (`torch.autograd.grad`), and enforce the Eikonal condition.

```python
import torch
import torch.nn as nn

class SinusoidalEncoding(nn.Module):
    """Frequency encoding mapping R^3 -> R^{3 + 6*num_frequencies}."""
    def __init__(self, num_frequencies: int = 6):
        super().__init__()
        self.frequencies = 2.0 ** torch.arange(num_frequencies)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        scaled = x.unsqueeze(-1) * self.frequencies.to(x.device) * torch.pi
        encoded = torch.cat([torch.sin(scaled), torch.cos(scaled)], dim=-1)
        return torch.cat([x, encoded.flatten(start_dim=1)], dim=-1)


class NeuralSDF(nn.Module):
    """Continuous coordinate MLP for Signed Distance Functions."""
    def __init__(self, hidden_dim: int = 128, num_layers: int = 4):
        super().__init__()
        self.encoder = SinusoidalEncoding(num_frequencies=4)
        in_dim = 3 + 3 * 2 * 4

        layers = []
        layers.append(nn.Linear(in_dim, hidden_dim))
        layers.append(nn.Softplus(beta=100))
        for _ in range(num_layers - 2):
            layers.append(nn.Linear(hidden_dim, hidden_dim))
            layers.append(nn.Softplus(beta=100))
        layers.append(nn.Linear(hidden_dim, 1))

        self.net = nn.Sequential(*layers)

    def forward(self, coords: torch.Tensor) -> torch.Tensor:
        return self.net(self.encoder(coords))


def compute_sdf_gradient_and_eikonal_loss(
    model: NeuralSDF,
    points: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Computes sdf values, spatial gradients, and the Eikonal loss.
    """
    points.requires_grad_(True)
    sdf = model(points)

    # Compute analytical spatial gradient df/dx
    grad = torch.autograd.grad(
        outputs=sdf,
        inputs=points,
        grad_outputs=torch.ones_like(sdf),
        create_graph=True,
        retain_graph=True
    )[0]

    # Eikonal penalty: (||grad|| - 1)^2
    grad_norm = torch.norm(grad, dim=-1)
    eikonal_loss = torch.mean((grad_norm - 1.0) ** 2)

    return sdf, eikonal_loss
```

---

## Zero-Level Set Extraction: Marching Cubes

Once a neural network $f_{\boldsymbol{\theta}}$ is trained, we can extract an explicit polygonal surface mesh by evaluating $f_{\boldsymbol{\theta}}$ over a regular 3D grid and applying the **Marching Cubes** algorithm. Because the representation is continuous, resolution is bounded only by GPU memory during sampling, rather than the native storage representation.

In our CVPR 2024 work on **Neural Implicit Morphing**, we extend this principle to time-varying homotopy manifolds $F(\mathbf{x}, t) = 0$, interpolating smoothly between disparate geometries while preserving critical facial landmarks and curvature.
