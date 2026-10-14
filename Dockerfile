FROM odoo:17.0

USER root

# Install essential Python packages for payment integrations, XML-RPC APIs, and cryptographic signatures
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    curl \
    && pip3 install --no-cache-dir --break-system-packages \
        stripe>=7.0.0 \
        requests>=2.31.0 \
        cryptography>=42.0.0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up custom addons permissions
RUN mkdir -p /mnt/extra-addons && chown -R odoo:odoo /mnt/extra-addons

USER odoo
