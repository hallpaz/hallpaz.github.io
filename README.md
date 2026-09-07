# Personal Academic & Research Website

A lightweight, zero-magic **Static Site Generator (SSG)** written in Python 3.11+ using the "Flask philosophy" (explicit over implicit). Compiles Markdown articles, structured YAML collections, and Jinja2 templates into a fully static `dist/` directory deployed to GitHub Pages.

---

## 🚀 Quick Start

### 1. Installation

Ensure Python 3.11+ is installed, then install the dependencies:

```bash
pip install -r requirements.txt
```

### 2. Local Development & Live Preview

Run the development server with automatic folder watching and live re-building on file saves:

```bash
python build.py --serve
```

Open your browser at [http://localhost:8000](http://localhost:8000). Any edits inside `content/`, `data/`, `templates/`, `static/`, or `config.yaml` will immediately trigger a rebuild.

To specify a custom port:

```bash
python build.py --serve --port 8080
```

### 3. Production Build

To perform a clean, one-shot production build:

```bash
python build.py --clean
```

The output will be generated inside the `dist/` folder.

---

## 📝 How to Add Content

### 1. Add a New Blog Post

Create a new Markdown file inside `content/blog/` (e.g. `content/blog/my-new-post.md`):

```markdown
---
title: "My New Article Title"
author: "Hallison Paz"          # Optional: defaults to site_name from config.yaml
date: 2024-07-01
tags: ["Machine Learning", "Mathematics"]
summary: "A short 1-2 sentence summary displayed on the blog index and RSS feed."
draft: false
---

Your Markdown content goes here.

### Math Support
- Inline math: $f(x) = \sum_{i=1}^n x_i^2$
- Display math:
$$\mathbf{x}_{adv} = \mathbf{x} + \epsilon \cdot \mathrm{sign}(\nabla_{\mathbf{x}} \mathcal{L}(\theta, \mathbf{x}, y))$$

### Code Highlighting
```python
import torch

def model_step(x):
    return x * 2.0
```
```

*Note: Reading time is automatically computed based on word count (~200 wpm).*

---

### 2. Add a Publication

Open `data/publications.yaml` and append a new entry:

```yaml
- title: "Neural Implicit Morphing of Face Images"
  authors: ["Guilherme Schardong", "Tiago Novello", "Hallison Paz", "Iurii Medvedev", "Luiz Velho"]
  me: "Hallison Paz"          # Automatically bolds your name in citations
  venue: "CVPR 2024"
  badge: "Oral"               # Optional badge: Oral, Spotlight, Best Paper, etc.
  date: 2024-06-17
  abstract: "We propose a continuous neural representation framework..."
  image: "/static/images/pubs/morphing.jpg"  # Optional preview image
  links:
    arxiv: "https://arxiv.org/abs/..."
    code: "https://github.com/..."
    project: "https://..."
    video: "https://..."
    bibtex: |
      @inproceedings{schardong2024neural,
        title={Neural Implicit Morphing of Face Images},
        author={...},
        year={2024}
      }
```

---

### 3. Add a News Item

Open `data/news.yaml` and append a new entry:

```yaml
- date: 2024-09-01
  tag: "New Position"
  title: "Joined École Polytechnique as a Postdoctoral Researcher"
  body: "I have officially joined the Laboratoire d'Informatique de l'École Polytechnique (LIX)..."
  link: "https://polytechnique.edu"  # Optional external URL (or null)
```

---

### 4. Add Teaching Courses

Open `data/teaching.yaml`:

```yaml
- year: 2024
  courses:
    - title: "Deep Reinforcement Learning"
      institution: "Institute of Technology and Leadership (Inteli)"
      role: "Instructor"
      url: null
      description: "Undergraduate curriculum covering MDPs, Q-Learning, and Policy Gradients."
```

---

### 5. Add Media & Talks

Open `data/media.yaml`:

```yaml
- type: "podcast"        # 'podcast' | 'youtube' | 'talk'
  title: "Adversarial Robustness and Neural Representations"
  source: "Neural Horizons AI Podcast"
  date: 2024-05-18
  duration: "1h 25m"
  description: "A 90-minute technical interview covering neural implicit surfaces..."
  url: "https://spotify.com"
  thumbnail: "/static/images/media/neural-horizons.jpg"
```

---

## 🛠️ Architecture & Features

- **No framework bloat:** Built purely with Python 3.11+, `Jinja2`, `markdown`, `Pygments`, and `python-frontmatter`.
- **KaTeX client-side math:** LaTeX math formulas (`$...$` and `$$...$$`) pass through untouched by Markdown, and are rendered in the browser with KaTeX auto-render (scoped to skip `<pre>`/`<code>`).
- **Pygments syntax highlighting:** Pygments generates `one-dark` CSS stylesheet at build time.
- **Light & Dark Theme:** Built with CSS custom variables, persisting user choice via `localStorage` with `prefers-color-scheme` fallback.
- **Clean URLs:** Routes are structured as `dist/<page>/index.html` (e.g. `/blog/understanding-adversarial-robustness/`).
- **Syndication & SEO:** Automatically produces `sitemap.xml` and an RSS 2.0 feed (`feed.xml`).
- **Automated Deployment:** GitHub Actions workflow in `.github/workflows/deploy.yml` builds on push to `main` and deploys `dist/` to GitHub Pages.
