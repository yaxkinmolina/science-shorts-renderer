# Science Shorts Free GitHub Renderer

This repository is a rendering worker for the n8n workflow:
`Science Shorts - 03 Verify and Render`.

## What it does

A `repository_dispatch` event sends a render manifest from n8n.

GitHub Actions then:

1. Installs FFmpeg and espeak-ng.
2. Generates vertical 720x1280 scene graphics.
3. Uses NASA Images search for `astronomy_image` scenes when an asset query is supplied.
4. Uses PubChem PUG REST for `molecule` scenes when a compound name is supplied.
5. Generates simple diagrams/spectrum cards for other scene types.
6. Creates a free prototype narration with espeak-ng.
7. Renders `science_short.mp4`.
8. Uploads the MP4 and metadata as a GitHub Actions artifact for 3 days.

## Setup

### 1. Create a repository

Create a GitHub repository named:

`science-shorts-renderer`

A public repository is recommended for this prototype because standard GitHub-hosted Actions runners are free for public repositories.

### 2. Upload these files

Your repository should contain:

```text
.github/
  workflows/
    render.yml

renderer/
  render.py
  requirements.txt
```

### 3. Create a fine-grained GitHub Personal Access Token

Give the token access only to this renderer repository.

Required repository permission for `repository_dispatch`:

- Contents: Read and write

Do not put the token into the workflow JSON itself.

### 4. Create an n8n Header Auth credential

In n8n create a Header Auth credential:

- Name: `Authorization`
- Value: `Bearer YOUR_GITHUB_TOKEN`

Select that credential in the `Dispatch GitHub Renderer` HTTP Request node.

### 5. Edit the n8n configuration

In `Normalize Stage 02 Package`, replace:

`REPLACE_WITH_YOUR_GITHUB_USERNAME`

with your GitHub username.

If you used a different repository name, also change:

`science-shorts-renderer`

### 6. Connect Groq

Select the same Groq credential you already use in:

`Groq - Source Verification`

### 7. Test

Run Stage 03 manually first.

If external verification passes, n8n dispatches the GitHub renderer and waits 120 seconds.

The final GitHub artifact name is:

`science-short-<job_id>`

It contains:

- `science_short.mp4`
- `render_metadata.json`
- `source_manifest.json`
- intermediate scene JPG files

## Important prototype limitation

The included voice is `espeak-ng`, chosen because it is completely free and predictable on GitHub Actions. It is intentionally a prototype voice. Once the workflow works end-to-end, replace only the TTS step with a better free/local TTS engine.

The current renderer also uses deliberately simple scientific graphics. The next version can add more specialized renderers for spectra, black-body curves, molecular structures, orbital diagrams, and reaction schemes.
