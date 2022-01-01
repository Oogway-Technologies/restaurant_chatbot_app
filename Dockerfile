# Extend the official Rasa SDK image
# Note: when updating make sure the version is in sync with:
# * rasa version in requirements.txt
# * RASA_VERSION and RASA_X_VERSION  in .github/workflows/continuous-deployment.yml
# Pull SDK image as base image
FROM rasa/rasa-sdk:2.8.2

# Use subdirectory as working directory
WORKDIR /app

# Copy any additional custom requirements, if necessary
COPY actions/requirements-actions.txt ./

# Change back to root user to install dependencies
USER root

# The following two RUNs are directly copied from
# https://github.com/RasaHQ/rasa-demo/blob/main/Dockerfile
# make sense to me to have them here as well
RUN apt-get update -qq && \
  apt-get install -y --no-install-recommends \
  python3 \
  python3-venv \
  python3-pip \
  python3-dev \
  # required by psycopg2 at build and runtime
  libpq-dev \
  # required for health check
  curl \
  && apt-get autoremove -y

# Make sure that all security updates are installed
RUN apt-get update && apt-get dist-upgrade -y --no-install-recommends

# Install extra requirements for actions code, if necessary
RUN pip install -r requirements-actions.txt

# Copy actions folder to working directory
COPY ./actions /app/actions
COPY ./const.py /app/

# By best practices, don't run the code with root user
USER 1001
