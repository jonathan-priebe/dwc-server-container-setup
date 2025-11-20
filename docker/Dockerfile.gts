# GTS Server (gamestats2) with Mono/.NET
# Based on pkmn-classic-framework

FROM debian:bullseye

LABEL maintainer="DWC Server"
LABEL description="Pokemon GTS Server using pkmn-classic-framework"

# Build arguments for database configuration
ARG GTS_DB_NAME=gts
ARG GTS_DB_USER=gts
ARG GTS_DB_PASSWORD=gts
ARG MARIADB_HOST=mariadb

# Environment variables
ENV GTS_DB_NAME=${GTS_DB_NAME}
ENV GTS_DB_USER=${GTS_DB_USER}
ENV GTS_DB_PASSWORD=${GTS_DB_PASSWORD}
ENV MARIADB_HOST=${MARIADB_HOST}

# Install dependencies
RUN apt-get update && apt-get install -y \
    apache2 \
    curl \
    git \
    gnupg \
    mariadb-client \
    mono-complete \
    libapache2-mod-mono \
    nuget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Clone and build pkmn-classic-framework
WORKDIR /tmp
RUN git clone --depth 1 https://github.com/jonathan-priebe/pkmn-classic-framework.git && \
    cd pkmn-classic-framework && \
    # Convert SSH to HTTPS for submodules
    sed -i -e 's/git@github\.com:/https:\/\/github.com\//g' .gitmodules && \
    git submodule update --init && \
    # Update connection strings (disable SSL for MariaDB compatibility)
    find ./ -name "*.config" -exec sed -i -e "s/Server=gts;/Server=${MARIADB_HOST};SslMode=None;/g" {} \; && \
    find ./ -name "*.config" -exec sed -i -e "s/Server=localhost;/Server=${MARIADB_HOST};SslMode=None;/g" {} \; && \
    find ./ -name "*.config" -exec sed -i -e "s/User Id=root;/User Id=${GTS_DB_USER};/g" {} \; && \
    find ./ -name "*.config" -exec sed -i -e "s/Password=;/Password=${GTS_DB_PASSWORD};/g" {} \; && \
    find ./ -name "*.config" -exec sed -i -e "s/Database=gts;/Database=${GTS_DB_NAME};/g" {} \; && \
    # Fix gts.csproj - remove problematic reference
    sed -i -e 's/<Reference Include="System.Web.Entity" \/>//g' gts/gts.csproj && \
    # Build GTS application
    cd gts && \
    nuget restore ../pkmn-classic-framework.sln || true && \
    xbuild /p:Configuration=Release /p:OutDir=publish/ && \
    mkdir -p /var/www/gts && \
    mv publish/_PublishedWebsites/gts/* /var/www/gts/ && \
    cd / && \
    rm -rf /tmp/pkmn-classic-framework

# Configure Apache with mod_mono
RUN a2dismod mpm_event && \
    a2enmod mpm_prefork && \
    # Create symlink for mod-mono-server2 to point to version 4
    ln -sf /usr/bin/mod-mono-server4 /usr/bin/mod-mono-server2 && \
    # Set global mod_mono server path to version 4
    echo 'MonoServerPath /usr/bin/mod-mono-server4' > /etc/apache2/conf-available/mono-server4.conf && \
    a2enconf mono-server4 && \
    # Create Apache config for GTS
    echo '<VirtualHost *:9002>\n\
    ServerAdmin webmaster@localhost\n\
    ServerName gamestats2.gs.nintendowifi.net\n\
    DocumentRoot /var/www/gts\n\
    MonoAutoApplication disabled\n\
    MonoApplications default "/:/var/www/gts"\n\
    <Location />\n\
        SetHandler mono\n\
        MonoSetServerAlias default\n\
    </Location>\n\
    ErrorLog ${APACHE_LOG_DIR}/gts-error.log\n\
    CustomLog ${APACHE_LOG_DIR}/gts-access.log combined\n\
</VirtualHost>' > /etc/apache2/sites-available/gts.conf && \
    a2dissite 000-default && \
    a2ensite gts && \
    # Add Listen directive for port 9002
    echo "Listen 9002" >> /etc/apache2/ports.conf

# Copy SQL dump
COPY gts/gts_dump.sql /gts_dump.sql

# Create entrypoint script
COPY docker/entrypoints/entrypoint.gts.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /var/www/gts

EXPOSE 9002

CMD ["/entrypoint.sh"]
