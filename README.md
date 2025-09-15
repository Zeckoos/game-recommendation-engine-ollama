# game-recommendation-engine-ollama
## Overview
This project is a game recommendation engine integrated with a local **Ollama3:8b** model and  **RAWG & Steam API**. It parses users' input and convert it into a **GameFilter** object with JSON formatting that is passed to RAWG API as the parameters to find matching games. The engine aims to provide detailed game metadata through enrichment from Steam API, match tags and genres that are distinguished via the LLM to the RAWG API, and allows filtering based on various criteria such as release date, price, genre, and platform. The system also includes caching mechanisms for faster metadata retrieval and supports automatic cache refresh for unknown tags, genres, or platforms. The current implementation has RAWG as the main search engine but support for other providers such as Epic, GOG, IsThereAnyDeals, etc. is planned in order to make the search engine interchangeable.

## Current Features
<ul>
  <li>Parse input into JSON format with a local Ollama model (Currently not very accurate/stable)</li>
  <li>Search for close/fuzzy matching games on RAWG</li>
  <li>Enrich game's information through Steam</li>
  <li>Match similar/custom genres/tags with RAWG's when possible</li>
  <li>Pre-fetch RAWG's "slugs" or IDs used for genres, platforms and tags, save as cache and load when available</li>                                                  
</ul>
