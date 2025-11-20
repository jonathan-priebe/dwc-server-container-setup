# GitHub Actions Workflows

## Pull Request Tests

**Workflow:** `pr-test.yml`

Runs automated tests on every pull request to main branch.

### Tests Included

| Job | Description |
|-----|-------------|
| **Lint** | Runs flake8, black, isort on Python code |
| **Test Admin** | Django checks, migrations, unit tests |
| **Test GameSpy** | Pytest for GameSpy server |
| **Build Images** | Builds Apache, Admin, GameSpy images |
| **Build GTS** | Builds GTS image (separate due to build time) |
| **Docker Compose** | Validates docker-compose.yml syntax |

### Trigger

Automatically runs on:
- Pull request opened to `main`
- Pull request synchronized (new commits)
- Pull request reopened

---

## GHCR Deployment

**Workflow:** `ghcr-deployment.yml`

Builds and pushes Docker images to GitHub Container Registry (GHCR).

### Triggers

#### Automatic

| Event | Description |
|-------|-------------|
| Push to `main` | Builds all images with `latest` tag |
| Version Tag `v*.*.*` | Builds all images with semver tags |

#### Manual

Via GitHub Actions UI → "Run workflow"

**Options:**
- `build_all` - Build all images (default: true)
- `build_apache` - Only Apache image
- `build_admin` - Only Admin image
- `build_gamespy` - Only GameSpy image
- `build_gts` - Only GTS image
- `tag` - Custom tag (default: latest)

### Images

| Image | Dockerfile | Description |
|-------|------------|-------------|
| `ghcr.io/{owner}/dwc-server-apache` | `docker/Dockerfile.apache-sslv3` | Apache Reverse Proxy |
| `ghcr.io/{owner}/dwc-server-admin` | `docker/Dockerfile.admin` | Django Admin Panel |
| `ghcr.io/{owner}/dwc-server-gamespy` | `docker/Dockerfile.gamespy` | NAS, GP, QR Server |
| `ghcr.io/{owner}/dwc-server-gts` | `docker/Dockerfile.gts` | Pokemon GTS Server |

### Tagging Strategy

#### On Version Tags (e.g. `v1.2.3`)

```
ghcr.io/{owner}/dwc-server-*:1.2.3
ghcr.io/{owner}/dwc-server-*:1.2
ghcr.io/{owner}/dwc-server-*:1
ghcr.io/{owner}/dwc-server-*:latest
ghcr.io/{owner}/dwc-server-*:sha-abc1234
```

#### On Push to main

```
ghcr.io/{owner}/dwc-server-*:latest
ghcr.io/{owner}/dwc-server-*:sha-abc1234
```

#### On Manual Trigger

```
ghcr.io/{owner}/dwc-server-*:{custom-tag}
ghcr.io/{owner}/dwc-server-*:sha-abc1234
```

### Creating a Release

```bash
# Commit changes
git add .
git commit -m "Release v1.0.0"

# Create version tag
git tag v1.0.0

# Push (including tags)
git push origin main --tags
```

The workflow will automatically start and create all images with the corresponding tags.

### Manual Deployment

1. Go to **Actions** → **Build and Push to GHCR**
2. Click **Run workflow**
3. Select branch and options
4. Click **Run workflow**

### Using the Images

After a successful build, the images can be used like this:

```yaml
# docker-compose.yml example
services:
  apache:
    image: ghcr.io/{owner}/dwc-server-apache:latest

  admin:
    image: ghcr.io/{owner}/dwc-server-admin:latest

  gamespy:
    image: ghcr.io/{owner}/dwc-server-gamespy:latest

  gts:
    image: ghcr.io/{owner}/dwc-server-gts:latest
```

Or with a specific version:

```yaml
services:
  apache:
    image: ghcr.io/{owner}/dwc-server-apache:1.0.0
```

### Prerequisites

- Repository must be on GitHub
- Packages must be enabled (Settings → Packages)
- `GITHUB_TOKEN` automatically has the required permissions

### Troubleshooting

**Build fails:**
- Check the logs in the Actions tab
- Ensure all Dockerfiles are present
- Verify the build context is correct

**Push to GHCR failed:**
- Check repository permissions
- Ensure Packages are enabled

**Image not visible:**
- Go to Packages tab in the repository
- Check Package Visibility settings
