# 🌐 Official IMD MetNet Circulars AI Index & Distribution Hub

This public repository hosts the live, crowd-sourced, AI-indexed circulars registry for the **Meteorological Portal Android Application**.

### 📡 Public Endpoints
* **Live AI Circulars Index (Fastly CDN):**  
  `https://raw.githubusercontent.com/Aman6390/metnet-circulars-index/main/circulars_ai_index.json`
* **Alternate Mirror:**  
  `https://raw.githubusercontent.com/Aman6390/metnet-circulars-index/main/data/circulars_ai_index.json`
* **Official Over-The-Air (OTA) APK Releases:**  
  `https://github.com/Aman6390/metnet-circulars-index/releases`

### 🤖 How Git AI Works
1. When any staff member's mobile app spots a newly published MetNet circular during periodic sync, it submits a ticket.
2. The automated **Git AI** GitHub Action (`git_ai_indexer.yml`) extracts the cadre, urgency, deadlines, and generates a plain-English executive summary.
3. The enriched circular metadata is committed to the public index and distributed to all employees automatically.
