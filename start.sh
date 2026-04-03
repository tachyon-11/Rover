echo "Starting Rover..."
open -a Docker
sleep 5
cd /Users/tachyon/Desktop/Rover
source venv/bin/activate
docker compose up -d
echo "Waiting for containers..."
sleep 5
docker ps
uvicorn backend.main:app --reload