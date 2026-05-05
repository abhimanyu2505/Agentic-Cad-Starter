FROM cadquery/cadquery:latest

# Set the working directory to /app inside the container
WORKDIR /app

RUN pip install openai pydantic streamlit plotly trimesh scipy

# Copy all local project files into the image's /app directory
COPY . /app

CMD ["python", "gear_engineering/main_pipeline.py"]
