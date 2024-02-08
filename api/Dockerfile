FROM python:3.11-buster
RUN useradd -ms /bin/bash admin
RUN pip install poetry==1.5.1
RUN poetry config virtualenvs.create false
RUN mkdir /app
WORKDIR /app
COPY ./pyproject.toml ./poetry.lock* ./
RUN poetry install --no-interaction --no-ansi --no-root --no-directory
COPY ./*.py ./
COPY ./*.env ./
COPY . .
RUN poetry install  --no-interaction --no-ansi
RUN chown -R admin:admin /app
RUN chmod 755 /app
USER admin
CMD exec uvicorn main:app --host 0.0.0.0 --port 8080