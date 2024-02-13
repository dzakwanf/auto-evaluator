sudo docker run -d  --name api-eval \
  -v "/home/dzakwan_falih/.config/":/app/credential:ro \
  --env GOOGLE_APPLICATION_CREDENTIALS=/app/credential/sa.json \
  -p 0.0.0.0:8080:8080 \
  api_eval