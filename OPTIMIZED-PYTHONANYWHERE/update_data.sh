#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"

mkdir -p data/fighters

cp ../../mma-ai/Scrapers/data/fighters/* data/fighters/
cp ../../mma-ai/Scrapers/data/event_data_sherdog.csv ../../mma-ai/Scrapers/data/fighter_info.csv data/

rm -f data/fighters.zip
(cd data && zip -qr fighters.zip fighters/*)

echo "Updated data files and created data/fighters.zip"
