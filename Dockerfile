# Use latest alpine-derived Python base image
FROM python:3-alpine

# Move to app directory

# Install requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source to app directory
COPY . .

# Make sure run script is executable
RUN chmod +rxxx ./run.sh

CMD sh run.sh