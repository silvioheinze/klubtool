FROM python:3.13-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3-dev \
        gcc \
        build-essential \
        libpq-dev \
        libxml2-dev \
        libxslt-dev \
        libffi-dev \
        zlib1g-dev \
        libjpeg-dev \
        tzdata \
        gettext \
        # WeasyPrint dependencies
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-xlib-2.0-0 \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Set timezone
ENV TZ=Europe/Vienna

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONPATH=/usr/src/app

# Set work directory
WORKDIR /usr/src/app

# Install dependencies
COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY ./app/ .