# Use a base image
FROM ubuntu:24.04

# Install necessary packages
RUN apt-get update && \
    apt-get install -y \
    wget \
    dpkg \
    git \
    libasound2t64 \
    libfreetype6 \
    libfontconfig1 \
    libx11-6 \
    libxext6 \
    libxi6 \
    libxrender1 \
    libxtst6 \
    zlib1g \
    fonts-dejavu \
    java-common \
    xz-utils \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY ./jre/zulu8-jre-amd64.deb /tmp/zulu8-jre.deb

COPY ./app/app-start.sh /app/app-start.sh

# Install the .deb package using dpkg
RUN dpkg -i /tmp/zulu8-jre.deb && \
    apt-get install -f -y && \
    rm -f /tmp/zulu8-jre.deb && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Verify the Java installation
RUN java -version

# Define environment variables for Mule and Java
ENV JAVA_HOME=/usr/lib/jvm/zulu8
ENV MULE_HOME=/mule/mule-1.3.3
ENV PATH=$MULE_HOME/bin:$PATH

CMD ["/app/app-start.sh"]
