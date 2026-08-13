FROM mcr.microsoft.com/devcontainers/base:ubuntu

# gh codespace ssh starts and configures this server with the ephemeral key
# issued by GitHub. Do not add the generic sshd feature: its independent
# entrypoint starts a second server without GitHub's key configuration.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      openssh-client \
      openssh-server \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /run/sshd
