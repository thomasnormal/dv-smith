# RockyLinux 9 has /bin/sh symlinked to bash, unlike Ubuntu where /bin/sh is dash.
# This is important for Cadence tools that expect /bin/sh to be bash.
FROM rockylinux:9

# Install system packages and Python tools in one layer
# First install EPEL and enable CRB repo (needed for bat, miller, parallel)
RUN dnf -y --setopt=install_weak_deps=False --setopt=tsflags=nodocs install epel-release dnf-plugins-core \
    && dnf config-manager --set-enabled crb \
    && dnf -y --setopt=install_weak_deps=False --setopt=tsflags=nodocs --nobest install \
      python3.12 python3.12-pip \
      which git make tmux \
      tcsh ksh libnsl libxcrypt-compat \
      fzf bat miller parallel \
    && dnf clean all \
    && rm -rf /var/cache/dnf \
    && python3.12 -m pip install --no-cache-dir pytest vcdvcd yq \
    && ln -sf /lib64/ld-linux-x86-64.so.2 /lib64/ld-lsb-x86-64.so.3

# The last line, copying ld-linux is some cadence thing.
# Cadence environment and test configuration
ENV PATH="/opt/cadence/installs/XCELIUM2403/bin:\
/opt/cadence/installs/XCELIUM2403/tools/bin/64bit:\
/opt/cadence/installs/VMANAGER2403/bin:\
${PATH}" \
    TB_HOME=/axi4_avip \
    TEST_NAME=student_example_32b_write_read_test

# Clone and prepare repository
RUN git clone --depth=1 https://github.com/mbits-mirafra/axi4_avip.git /axi4_avip

# Copy only the clean_repo script and non-solution resources
COPY resources/clean_repo.sh /tmp/clean_repo.sh
COPY resources/coverage_requirements.txt /resources/coverage_requirements.txt
COPY resources/AGENTS.md /resources/AGENTS.md

# Setup repository and create directories in one layer
RUN bash /tmp/clean_repo.sh \
    && rm /tmp/clean_repo.sh \
    && mkdir -p /tests /oracle \
    && chown -R 1000:1000 /axi4_avip /tests /resources

# Smoke test - verify critical tools are accessible
# TRIAGE tools: fzf (fuzzy finder), bat (syntax viewer), yq (YAML), mlr (CSV), parallel
CMD ["bash", "-c", "\
  xrun -version \
  && imc -help \
  && which make \
  && which python3.12 \
  && which tmux \
  && which fzf \
  && which bat \
  && which yq \
  && which mlr \
  && which parallel \
  && which vcdcat \
  && which python -c 'import vcdvcd' \
  && echo 'All tools verified'"]

# Set current working directory to TB_HOME
WORKDIR $TB_HOME