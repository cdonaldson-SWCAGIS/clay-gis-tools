# Use the official ArcGIS Python API Docker image as base
FROM ghcr.io/esri/arcgis-python-api-notebook

# Switch to root user to install additional packages
USER root

# Install additional system dependencies if needed
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    krb5-user \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set the working directory
WORKDIR /app

# Copy requirements file first (for better Docker caching)
COPY requirements.txt .

# Install arcgis-mapping via conda from the esri channel
# This must be done before pip installs to ensure proper dependencies
RUN conda install -y -c esri arcgis-mapping

# Install additional Python packages for your application
# The base image already includes arcgis, but we'll upgrade/reinstall to ensure compatibility
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy the rest of the application files
COPY . .

# Create a non-root user for running the application (if not already present)
# The base image already has a notebook user, but we'll ensure proper permissions
RUN chown -R ${NB_UID}:${NB_GID} /app

# Expose the Streamlit port
EXPOSE 8501

# Switch back to the notebook user (security best practice)
USER ${NB_UID}

# Set environment variables for better Streamlit behavior in containers
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Run Streamlit application
CMD ["streamlit", "run", "app.py"]
