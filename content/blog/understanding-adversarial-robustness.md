---
title: "Understanding Adversarial Robustness: Geometry, Gradients, and Defenses"
author: "Hallison Paz"
date: 2024-05-12
tags: ["Machine Learning", "Adversarial Robustness", "PyTorch", "Geometry"]
summary: "A mathematical intuition and code walkthrough of how imperceptible perturbations confuse deep neural networks, and how robust optimization alters decision manifolds."
lang: "en"
draft: true
---

Deep neural networks achieve superhuman accuracy on benchmark visual tasks, yet remain notoriously fragile when exposed to small, maliciously crafted perturbations. An image of a panda can be turned into a gibbon with 99% model confidence by adding imperceptible noise bounded by $\|\boldsymbol{\delta}\|_\infty \le \epsilon$.

In this post, we unpack the mathematical geometry of adversarial examples, derive standard white-box attacks from first principles, and implement Projected Gradient Descent (PGD) in PyTorch.

---

## The Geometry of High-Dimensional Hyperspheres

Why are neural networks vulnerable in the first place? A widespread early misconception attributed adversarial examples to extreme non-linearities and "pockets" in the manifold. However, Goodfellow et al. demonstrated that the **linearity in high-dimensional spaces** is sufficient to explain the vulnerability.

Consider a linear classifier with weight vector $\mathbf{w} \in \mathbb{R}^d$ and bias $b \in \mathbb{R}$. Given an input $\mathbf{x} \in \mathbb{R}^d$, the activation is:

$$\hat{y} = \mathbf{w}^\top \mathbf{x} + b$$

Now let us add an adversarial perturbation $\boldsymbol{\eta} \in \mathbb{R}^d$ subject to the $\ell_\infty$ constraint $\|\boldsymbol{\eta}\|_\infty \le \epsilon$, meaning $|\eta_i| \le \epsilon$ for every dimension $i \in \{1, \dots, d\}$:

$$\hat{y}_{adv} = \mathbf{w}^\top (\mathbf{x} + \boldsymbol{\eta}) + b = \mathbf{w}^\top \mathbf{x} + b + \mathbf{w}^\top \boldsymbol{\eta}$$

To maximize the activation shift, we choose $\boldsymbol{\eta} = \epsilon \cdot \mathrm{sign}(\mathbf{w})$. The perturbation term then evaluates to:

$$\mathbf{w}^\top \boldsymbol{\eta} = \epsilon \sum_{i=1}^d |w_i| = \epsilon \|\mathbf{w}\|_1$$

If the average magnitude of an element in $\mathbf{w}$ is $m$, then $\|\mathbf{w}\|_1 = d \cdot m$. In an input space with $d = 3 \times 224 \times 224 \approx 150{,}528$ dimensions, even a miniscule $\epsilon = 0.007$ produces an aggregate activation shift proportional to $150{,}528 \times 0.007 \times m \approx 1053 \cdot m$, which is more than enough to completely overpower the true signal!

---

## Deriving the Fast Gradient Sign Method (FGSM)

For a general non-linear neural network parameterized by $\boldsymbol{\theta}$ with loss function $\mathcal{L}(\boldsymbol{\theta}, \mathbf{x}, y)$, we can linearly approximate the loss surface around $\mathbf{x}$ using a first-order Taylor expansion:

$$\mathcal{L}(\boldsymbol{\theta}, \mathbf{x} + \boldsymbol{\delta}, y) \approx \mathcal{L}(\boldsymbol{\theta}, \mathbf{x}, y) + \nabla_{\mathbf{x}} \mathcal{L}(\boldsymbol{\theta}, \mathbf{x}, y)^\top \boldsymbol{\delta}$$

Under the $\ell_\infty$ constraint $\|\boldsymbol{\delta}\|_\infty \le \epsilon$, the perturbation that maximizes this local linear approximation is:

$$\boldsymbol{\delta}^* = \epsilon \cdot \mathrm{sign}\left(\nabla_{\mathbf{x}} \mathcal{L}(\boldsymbol{\theta}, \mathbf{x}, y)\right)$$

This yields the canonical **Fast Gradient Sign Method (FGSM)** adversary:

$$\mathbf{x}_{adv} = \mathrm{clip}_{[\mathbf{0}, \mathbf{1}]}\left(\mathbf{x} + \epsilon \cdot \mathrm{sign}\left(\nabla_{\mathbf{x}} \mathcal{L}(\boldsymbol{\theta}, \mathbf{x}, y)\right)\right)$$

---

## Projected Gradient Descent (PGD)

FGSM takes a single large step in the direction of the sign gradient. However, the loss landscape of a deep neural network is non-convex. By taking multiple smaller steps and projecting back into the feasible $\epsilon$-ball $\mathcal{S} = \{\mathbf{x}' : \|\mathbf{x}' - \mathbf{x}\|_p \le \epsilon\} \cap [0, 1]^d$, we arrive at **Projected Gradient Descent (PGD)**, regarded as the standard first-order adversary:

$$\mathbf{x}^{(t+1)} = \Pi_{\mathbf{x} + \mathcal{S}}\left( \mathbf{x}^{(t)} + \alpha \cdot \mathrm{sign}\left(\nabla_{\mathbf{x}^{(t)}} \mathcal{L}(\boldsymbol{\theta}, \mathbf{x}^{(t)}, y)\right) \right)$$

where $\alpha$ is the step size and $\Pi$ denotes the projection operator.

```python
import torch
import torch.nn as nn

def pgd_attack(
    model: nn.Module,
    images: torch.Tensor,
    labels: torch.Tensor,
    eps: float = 8 / 255,
    alpha: float = 2 / 255,
    steps: int = 10,
    random_start: bool = True
) -> torch.Tensor:
    """
    Projected Gradient Descent (PGD) Linf attack.
    """
    loss_fn = nn.CrossEntropyLoss()
    adv_images = images.clone().detach()

    if random_start:
        # Uniform initialization within [-eps, eps]
        adv_images += torch.empty_like(adv_images).uniform_(-eps, eps)
        adv_images = torch.clamp(adv_images, min=0.0, max=1.0)

    for step in range(steps):
        adv_images.requires_grad = True
        outputs = model(adv_images)
        loss = loss_fn(outputs, labels)

        grad = torch.autograd.grad(
            loss, adv_images, retain_graph=False, create_graph=False
        )[0]

        # Ascent step + Linf projection + pixel valid range clip
        adv_images = adv_images.detach() + alpha * grad.sign()
        eta = torch.clamp(adv_images - images, min=-eps, max=eps)
        adv_images = torch.clamp(images + eta, min=0.0, max=1.0).detach()

    return adv_images
```

---

## Min-Max Robust Optimization

To defend against such attacks, Madry et al. framed adversarial defense as a saddle point problem (min-max game):

$$\min_{\boldsymbol{\theta}} \mathbb{E}_{(\mathbf{x}, y) \sim \mathcal{D}} \left[ \max_{\boldsymbol{\delta} \in \mathcal{S}} \mathcal{L}(\boldsymbol{\theta}, \mathbf{x} + \boldsymbol{\delta}, y) \right]$$

The inner maximization corresponds to finding the most damaging perturbation (via PGD), while the outer minimization adjusts network weights $\boldsymbol{\theta}$ to minimize loss on those adversarial inputs.

Geometrically, adversarial training flattens the loss curvature along the directions normal to the decision boundary, pushing the decision manifold away from the data distribution.

---

## Conclusion & Next Steps

Adversarial vulnerability is fundamentally geometric: in high dimensions, most points lie extremely close to the decision boundary. Future work in neural implicit representations explores whether continuous geometric priors can impart natural inductive biases that resist high-frequency adversarial noise.
