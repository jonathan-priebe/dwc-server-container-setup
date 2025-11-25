FROM debian:stable-slim

# Base tools
RUN apt-get update && apt-get install -y \
    wget curl git gnupg ca-certificates python3 python3-pip python3-yaml unzip && \
    curl https://download.mono-project.com/repo/xamarin.gpg | gpg --dearmor > /usr/share/keyrings/mono.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/mono.gpg] https://download.mono-project.com/repo/debian stable main" \
      > /etc/apt/sources.list.d/mono-official.list && \
    apt-get update && \
    apt-get install -y mono-complete msbuild && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /work

RUN mkdir -p /work/bin

# Clone and build MysteryGiftConvert with msbuild
RUN git clone https://github.com/jonathan-priebe/MysteryGiftConvert.git /work/MysteryGiftConvert && \
    ls -la /work/MysteryGiftConvert && \
    xbuild /work/MysteryGiftConvert/MysteryGiftConvert.csproj /p:Configuration=Release && \
    cp /work/MysteryGiftConvert/bin/Release/* /work/bin/

# Wrapper with mono
RUN echo '#!/bin/sh\nexec mono /work/bin/MysteryGiftConvert.exe "$@"' > /work/bin/MysteryGiftConvert && \
    chmod +x /work/bin/MysteryGiftConvert

# Prepare directories
RUN mkdir -p /work/config /work/tmp /work/DLC

# Scripts and configs
COPY run.sh /work/run.sh
COPY mg_pipeline.py /work/mg_pipeline.py
COPY config/mapping.yml /work/config/mapping.yml

RUN chmod +x /work/run.sh
