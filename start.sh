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


# Temporrary reset commands for deleting -> Using currenlty to clean everything testing
# Drop and recreate table (wipes all file records)
#docker exec -it sfo_postgres psql -U sfo_user -d smart_file_organizer -c "DROP TABLE IF EXISTS files;"

# Delete the entire collection
# python3 -c "
# import chromadb
# client = chromadb.HttpClient(host='localhost', port=8001)
# client.delete_collection('files')
# print('ChromaDB collection deleted ✅')
# "