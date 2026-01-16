# Fly.io Deployment Guide

This guide covers deploying the Clay GIS Tools application to Fly.io.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Environment Variables](#environment-variables)
- [Monitoring and Logs](#monitoring-and-logs)
- [Scaling](#scaling)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)

## Prerequisites

Before deploying to Fly.io, ensure you have:

1. **Fly.io Account**: Sign up at [fly.io](https://fly.io) if you haven't already
2. **Fly CLI**: Install the Fly.io CLI tool
   ```bash
   # macOS/Linux
   curl -L https://fly.io/install.sh | sh

   # Windows (PowerShell)
   powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
   ```
3. **Docker**: Required for building the application image
4. **ArcGIS Credentials**: Your ArcGIS Online/Portal username and password

## Initial Setup

### 1. Login to Fly.io

```bash
fly auth login
```

### 2. Initialize Your App (First Time Only)

If this is your first deployment, you'll need to create the app:

```bash
cd deploy
fly launch
```

This will:
- Create a new app on Fly.io
- Generate a `fly.toml` configuration file (already exists in this project)
- Optionally set up a PostgreSQL database (not required for this app)

**Note**: The `fly.toml` file is already configured for this project. If prompted to overwrite, choose "No" to keep the existing configuration.

### 3. Verify Configuration

Review the `fly.toml` file to ensure settings match your requirements:

- **App Name**: `clay-gis-tools` (can be changed if needed)
- **Primary Region**: `lax` (Los Angeles)
- **Memory**: `1gb`
- **CPU**: 1 shared CPU
- **Port**: `8501` (Streamlit default)

## Configuration

### Environment Variables

Set required environment variables using Fly.io secrets:

```bash
fly secrets set ARCGIS_USERNAME=your_username
fly secrets set ARCGIS_PASSWORD=your_password
```

Optional environment variables:

```bash
fly secrets set DEBUG_MODE=True  # Enable debug mode by default
fly secrets set MAP_SUFFIX="_Copy"  # Suffix for copied web maps
```

### View Current Secrets

```bash
fly secrets list
```

### Remove Secrets

```bash
fly secrets unset VARIABLE_NAME
```

## Deployment

### Build and Deploy

**Important**: The Dockerfile references files from the project root (like `requirements.txt`, `backend/`, `frontend/`, etc.), so you must deploy from the project root directory with the project root as the build context:

```bash
# From the project root directory
fly deploy . --config deploy/fly.toml --dockerfile deploy/Dockerfile
```

Or simply:

```bash
# From the project root directory (fly.toml dockerfile setting will be overridden)
fly deploy --config deploy/fly.toml --dockerfile deploy/Dockerfile
```

This command will:
1. Use the project root (`.`) as the build context
2. Build the Docker image using `deploy/Dockerfile` (paths in Dockerfile are relative to build context)
3. Push the image to Fly.io
4. Deploy the application
5. Start the application

**Note**: The build context is set by where you run `fly deploy` from. Since the Dockerfile uses paths like `COPY requirements.txt`, `COPY backend/`, etc., these must be relative to the project root, which is why we deploy from there.

### Deployment Options

**Deploy without building** (if image is already built):
```bash
fly deploy --no-build
```

**Deploy with remote builder** (faster builds):
```bash
fly deploy --remote-only
```

**Deploy to a specific region**:
```bash
fly deploy --region ord  # Chicago
```

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ARCGIS_USERNAME` | ArcGIS Online/Portal username | `your_username` |
| `ARCGIS_PASSWORD` | ArcGIS Online/Portal password | `your_password` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG_MODE` | Enable debug mode (simulate operations) | `True` |
| `MAP_SUFFIX` | Suffix for copied web maps | `"_Copy"` |

### Setting Environment Variables

**Using Fly Secrets** (Recommended for sensitive data):
```bash
fly secrets set ARCGIS_USERNAME=username ARCGIS_PASSWORD=password
```

**Using fly.toml** (For non-sensitive configuration):
Add to `fly.toml`:
```toml
[env]
  DEBUG_MODE = "True"
  MAP_SUFFIX = "_Copy"
```

## Monitoring and Logs

### View Application Logs

```bash
fly logs
```

### Follow Logs in Real-Time

```bash
fly logs --follow
```

### View Logs for Specific App

```bash
fly logs -a clay-gis-tools
```

### Check Application Status

```bash
fly status
```

### View Application Info

```bash
fly info
```

### Open Application in Browser

```bash
fly open
```

This will open your application at `https://clay-gis-tools.fly.dev` (or your custom domain).

## Scaling

### Current Configuration

The app is configured with:
- **Auto-scaling**: Machines auto-stop when idle and auto-start on request
- **Min Machines**: 0 (machines stop when not in use)
- **Memory**: 1GB
- **CPU**: 1 shared CPU

### Scale Up Resources

**Increase Memory**:
```bash
fly scale memory 2048  # 2GB
```

**Increase CPU**:
```bash
fly scale count 1 --vm-size shared-cpu-2x  # 2 CPUs
```

**Scale to Multiple Regions**:
```bash
fly regions add ord  # Add Chicago region
```

### Scale Configuration

Edit `fly.toml` to change scaling behavior:

```toml
[http_service]
  auto_stop_machines = 'stop'  # or 'suspend'
  auto_start_machines = true
  min_machines_running = 1  # Keep at least 1 machine running
```

Then redeploy:
```bash
fly deploy
```

## Troubleshooting

### Application Won't Start

1. **Check logs**:
   ```bash
   fly logs
   ```

2. **Verify environment variables**:
   ```bash
   fly secrets list
   ```

3. **Check application status**:
   ```bash
   fly status
   ```

### Build Failures

1. **Check Dockerfile**:
   Ensure the Dockerfile path is correct in your deployment command

2. **Verify requirements**:
   The Dockerfile references `requirements.txt`. Ensure this file exists in the project root.

3. **Build locally first**:
   ```bash
   docker build -f deploy/Dockerfile -t clay-gis-tools .
   ```

### Connection Issues

1. **Verify port configuration**:
   Ensure `internal_port = 8501` in `fly.toml` matches Streamlit's port

2. **Check firewall/network**:
   Fly.io apps are accessible via HTTPS by default

### Authentication Issues

1. **Verify credentials**:
   ```bash
   fly secrets list
   ```

2. **Update credentials**:
   ```bash
   fly secrets set ARCGIS_USERNAME=new_username ARCGIS_PASSWORD=new_password
   ```

3. **Restart the app**:
   ```bash
   fly apps restart clay-gis-tools
   ```

### View Machine Details

```bash
fly machine list
fly machine status <machine-id>
```

### SSH into Machine

```bash
fly ssh console
```

## Maintenance

### Update Application

1. **Pull latest changes**:
   ```bash
   git pull
   ```

2. **Redeploy**:
   ```bash
   cd deploy
   fly deploy
   ```

### Restart Application

```bash
fly apps restart clay-gis-tools
```

### Stop Application

```bash
fly apps stop clay-gis-tools
```

### Delete Application

**Warning**: This permanently deletes your application and all associated data.

```bash
fly apps destroy clay-gis-tools
```

### Backup Configuration

Your `fly.toml` file is version controlled, but secrets are not. Document your secret values securely (use a password manager).

### Update Fly CLI

```bash
# macOS/Linux
curl -L https://fly.io/install.sh | sh

# Windows
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

## Custom Domain

### Add Custom Domain

1. **Add domain to Fly.io**:
   ```bash
   fly certs add yourdomain.com
   ```

2. **Update DNS**:
   Follow the instructions provided by Fly.io to update your DNS records

3. **Verify certificate**:
   ```bash
   fly certs show yourdomain.com
   ```

## Cost Optimization

### Current Setup

- **Auto-stop/start**: Machines stop when idle (saves costs)
- **Min machines**: 0 (no machines running when idle)
- **Shared CPU**: More cost-effective than dedicated CPUs

### Cost Considerations

- Machines are billed per second of runtime
- Storage is billed separately
- Bandwidth is included in most plans
- Auto-stopping machines significantly reduces costs for low-traffic apps

### Monitor Usage

```bash
fly dashboard
```

Visit the Fly.io dashboard to monitor usage and costs.

## Additional Resources

- [Fly.io Documentation](https://fly.io/docs/)
- [Fly.io CLI Reference](https://fly.io/docs/flyctl/)
- [Streamlit Deployment Guide](https://docs.streamlit.io/deploy)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

## Support

For Fly.io-specific issues:
- [Fly.io Community](https://community.fly.io/)
- [Fly.io Support](https://fly.io/support/)

For application-specific issues:
- Check the main [README.md](../README.md)
- Review application logs: `fly logs`
