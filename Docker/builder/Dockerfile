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

# Download and install Maven
RUN wget https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.9/apache-maven-3.9.9-bin.tar.gz && \
    tar -xzf apache-maven-3.9.9-bin.tar.gz && \
    mv apache-maven-3.9.9 /opt/maven && \
    ln -s /opt/maven/bin/mvn /usr/bin/mvn && \
    rm -f apache-maven-3.9.9-bin.tar.gz

# Define environment variables for Maven
ENV MAVEN_HOME=/opt/maven
ENV PATH=$MAVEN_HOME/bin:$PATH

COPY ./jdk/zulu8-jdk-amd64.deb /tmp/zulu8-jdk.deb

# Install the .deb package using dpkg
RUN dpkg -i /tmp/zulu8-jdk.deb && \
    apt-get install -f -y && \
    rm -f /tmp/zulu8-jdk.deb && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Verify the Java installation
RUN java -version

# Define environment variables for Java
ENV JAVA_HOME=/usr/lib/jvm/zulu-8-amd64
