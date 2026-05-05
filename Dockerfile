FROM cadquery/cadquery:latest

# Set the working directory to /app inside the container
WORKDIR /app

RUN pip install openai pydantic streamlit plotly trimesh scipy pytest

# Copy all local project files into the image's /app directory
COPY . /app

# Create outputs directory for debug artifacts and exports
RUN mkdir -p /app/outputs

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
