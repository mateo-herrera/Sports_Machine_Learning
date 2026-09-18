import { useState, useEffect } from 'react';

const API_URL = '/api/games';

export function useGames() {
  const [games, setGames] = useState([]);
  const [modelAccuracy, setModelAccuracy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(API_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (data.error) throw new Error(data.error);
        setGames(data.games);
        setModelAccuracy(data.model_accuracy);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return { games, modelAccuracy, loading, error };
}