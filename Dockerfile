FROM python:3.13-slim

WORKDIR /app

# Install only necessary dependencies
RUN pip install --no-cache-dir pyparsing

# Copy the script
COPY fp-kicad8-to-ergogen.py .

# Create default output directory
RUN mkdir -p ergogen

# Set the entrypoint to the script
ENTRYPOINT ["python3", "fp-kicad8-to-ergogen.py"]
