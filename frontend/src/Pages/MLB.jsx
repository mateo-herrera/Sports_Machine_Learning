import mlblogo from '../../assests/mlb.svg'
import accuracy_icon from '../../assests/accuracy_icon.png'
import today_icon from '../../assests/today_icon.png'
import tomorrow_icon from '../../assests/tomorrow_icon.png'

import { useGames } from '../hooks/useGames';

export function MLB_Page() {

    // Dates
    const date = new Date()

    const today_date = date.toLocaleDateString()

    const tomorrow = new Date(date)
    tomorrow.setDate(date.getDate() + 1)

    const tomorrows_date = tomorrow.toLocaleDateString()

    const logo = (id) => `https://www.mlbstatic.com/team-logos/${id}.svg`;

    // Date strings in 'YYYY-MM-DD' format to match backend's 'date' field
    function toLocalDateString(d) {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    const pct = (v) => (v == null ? '—' : `${(v * 100).toFixed(0)}%`);

    const edge = (a, b) => (a == null || b == null ? null : (a - b) * 100);

    function edgeStyle(e) {
        if (e == null) return 'text-[#888]';
        if (e < 0) return 'text-red-400';
        if (e > 5) return 'text-green-400';
        return 'text-yellow-400';
    }

    function game_status_headerStyle(game) {
        if (game.is_live) return 'text-[#b8444a]';
        if (game.is_final) return 'text-[#666]';
        return 'text-[#888]';
    }

    function formatEdge(e) {
        if (e == null) return '—';
        return `${e > 0 ? '+' : ''}${e.toFixed(1)}`;
    }

    const todayStr = toLocalDateString(date);
    const tomorrowStr = toLocalDateString(tomorrow);

    //Get Stats
    const { games, modelAccuracy, loading, error } = useGames();

    if (loading) return <div className='h-[80vh] text-white font-bold text-[2rem] flex justify-center items-center'>Loading games...</div>;
    if (error) return <div className='h-[80vh] text-white font-bold text-[2rem] flex justify-center items-center'>Error loading games: {error}</div>;

    //split games into today and tomorrow
    const todayGames = games.filter((g) => g.date === todayStr);
    const tomorrowGames = games.filter((g) => g.date === tomorrowStr);

  return (
    
    <div className="bg-[#030d1f] min-h-screen">
        {/* Header with mlb logo */}
        <div className="bg-[#000f26] flex justify-center border-3 border-[#2c3442]">
            <img src={mlblogo} alt="MLB" className="w-13 h-13" />
        </div>

        {/* Total games today and Total games Tomorrow and Model Accuracy */}
        <div className="mt-2 flex gap-2 w-[95%] mx-auto">
            
            {/* Card */}
            <div className="flex-1 bg-[#131d2e] border-2 border-[#2c3442] rounded-lg px-2 py-1">
                {/* Image */}
                <div className="flex justify-center">
                    <img src={today_icon} alt="today" className="w-10 h-10"/>
                </div>
                {/* Bottom row */}
                <div className="flex justify-between items-end mt-1">
                    <p className="text-[#c7c7c7] font-bold text-[.8rem]">
                        Today's Games
                    </p>
                    <p className="text-white text-[1.7rem] font-bold">
                        {todayGames.length}
                    </p>
                </div>
            </div>
            {/* Card */}
            <div className="flex-1 bg-[#131d2e] border-2 border-[#2c3442] rounded-lg px-2 py-1">
                {/* Image */}
                <div className="flex justify-center">
                    <img src={tomorrow_icon} alt="today" className="w-10 h-10"/>
                </div>
                {/* Bottom row */}
                <div className="flex justify-between items-end mt-1">
                    <p className="text-[#c7c7c7] font-bold text-[.8rem]">
                        Tmrw's Games
                    </p>
                    <p className="text-white text-[1.7rem] font-bold">
                    {/* Number of games */}
                        {tomorrowGames.length}
                    </p>
                </div>
            </div>
            {/* Card */}
            <div className="flex-1 bg-[#131d2e] border-2 border-[#2c3442] rounded-lg px-2 py-1">
                {/* Image */}
                <div className="flex justify-center">
                    <img src={accuracy_icon} alt="accuracy" className="w-10 h-10"/>
                </div>
                {/* Bottom row */}
                <div className="flex justify-between items-end mt-1">
                    <p className="text-[#c7c7c7] font-bold text-[.8rem]">
                        Model Accuracy
                    </p>
                    <p className="text-white text-[1.7rem] font-bold">
                    {/* Model Accuarcy */}
                        {(modelAccuracy * 100).toFixed(1)}
                    </p>
                    <p className="text-white text-[.8rem] font-bold mb-2">
                        %
                    </p>
                </div>
            </div>

        </div>        


        {/* Todays Games */}
        <div className="w-[95%] mx-auto mb-1 mt-3 box-border rounded-lg border-2 border-[#2c3442] bg-[#131d2e] text-white">
            <div className="flex justify-between px-4 py-2">
                <span className='text-[1rem] font-bold'>Today's Games</span>
                <span className='text-[.9rem] font-light text-[#c7c7c7]'>{today_date}</span>
            </div>
        </div>

        {todayGames.map((game) => {
            const awayEdge = edge(game.away_prediction, game.away_polymarket);
            const homeEdge = edge(game.home_prediction, game.home_polymarket);

            return (
                <div
                    key={game.game_id}
                    className="w-[80%] bg-[#232b38] border-2 border-[#2c3442] rounded-lg p-1 text-white mx-auto mt-2 mb-2"
                >
                    <div className="flex justify-center items-center gap-2">
                        {game.is_live && (
                            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                        )}
                        <p className={`text-[1rem] ${game_status_headerStyle(game)}`}>
                            {game.is_live ? (game.inning || 'Live')
                                : game.is_final ? 'Final'
                                : game.time}
                        </p>
                    </div>

                    <div className="grid grid-cols-2">

                        {/* Away Team */}
                        <div className="text-center border-r border-[#2c3442]">
                            <img
                                src={logo(game.away_team_id)}
                                alt=""
                                className="w-10 h-10 mx-auto mb-1"
                                onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }}
                            />
                            <p className="font-bold text-[1.2rem]">
                                {game.away}
                            </p>

                            <div className="mt-1">
                                <p className="text-[#888] text-[.8rem]">
                                    MODEL
                                </p>
                                <p className="font-bold text-[1rem]">
                                    {pct(game.away_prediction)}
                                </p>
                            </div>

                            <div className="mt-1">
                                <p className="text-[#888] text-[.8rem]">
                                    POLYMARKET
                                </p>
                                <p className="font-bold text-[1rem]">
                                    {pct(game.away_polymarket)}
                                </p>
                            </div>

                            <div className="mt-1">
                                <p className="text-[#888] text-[.8rem]">
                                    EDGE
                                </p>
                                <p className={`font-bold text-[1rem] ${edgeStyle(awayEdge)}`}>
                                    {formatEdge(awayEdge)}
                                </p>
                            </div>
                        </div>

                        {/* Home Team */}
                        <div className="text-center">
                            <img
                                src={logo(game.home_team_id)}
                                alt=""
                                className="w-10 h-10 mx-auto mb-1"
                                onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }}
                            />
                            <p className="font-bold text-[1.2rem]">
                                {game.home}
                            </p>

                            <div className="mt-1">
                                <p className="text-[#888] text-[.8rem]">
                                    MODEL
                                </p>
                                <p className="font-bold text-[1rem]">
                                    {pct(game.home_prediction)}
                                </p>
                            </div>

                            <div className="mt-1">
                                <p className="text-[#888] text-[.8rem]">
                                    POLYMARKET
                                </p>
                                <p className="font-bold text-[1rem]">
                                    {pct(game.home_polymarket)}
                                </p>
                            </div>

                            <div className="mt-1">
                                <p className="text-[#888] text-[.8rem]">
                                    EDGE
                                </p>
                                <p className={`font-bold text-[1rem] ${edgeStyle(homeEdge)}`}>
                                    {formatEdge(homeEdge)}
                                </p>
                            </div>
                        </div>

                    </div>
                </div>
            );
        })}
        
        

        {/*Tomorrows Games */}
        <div className="w-[95%] mx-auto mb-1 mt-3 box-border rounded-lg border-2 border-[#2c3442] bg-[#131d2e] text-white">
            <div className="flex justify-between px-4 py-2">
                <span className='text-[1rem] font-bold'>Tomorrows's Games</span>
                <span className='text-[.9rem] font-light text-[#c7c7c7]'>{tomorrows_date}</span>
            </div>
        </div>

        {/* Maps Tomorrows games to cards */}
        {tomorrowGames.map((game) => {
            const awayEdge = edge(game.away_prediction, game.away_polymarket);
            const homeEdge = edge(game.home_prediction, game.home_polymarket);

            return (
                <div
                    key={game.game_id}
                    className="w-[80%] bg-[#232b38] border-2 border-[#2c3442] rounded-lg p-1 text-white mx-auto mt-2 mb-2"
                >
                    <div className="flex justify-center items-center gap-2">
                        {game.is_live && (
                            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                        )}
                        <p className="text-[#888] text-[1rem]">
                            {game.is_live ? (game.inning || 'Live')
                                : game.is_final ? 'Final'
                                : game.time}
                        </p>
                    </div>

                    <div className="grid grid-cols-2">

                        {/* Away Team */}
                        <div className="text-center border-r border-[#2c3442]">
                            <img
                                src={logo(game.away_team_id)}
                                alt=""
                                className="w-10 h-10 mx-auto mb-1"
                                onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }}
                            />
                            <p className="font-bold text-[1.2rem]">
                                {game.away}
                            </p>

                            <div className="mt-1">
                                <p className="text-[#888] text-[.8rem]">
                                    MODEL
                                </p>
                                <p className="font-bold text-[1rem]">
                                    {pct(game.away_prediction)}
                                </p>
                            </div>

                            <div className="mt-1">
                                <p className="text-[#888] text-[.8rem]">
                                    POLYMARKET
                                </p>
                                <p className="font-bold text-[1rem]">
                                    {pct(game.away_polymarket)}
                                </p>
                            </div>

                            <div className="mt-1">
                                <p className="text-[#888] text-[.8rem]">
                                    EDGE
                                </p>
                                <p className={`font-bold text-[1rem] ${edgeStyle(awayEdge)}`}>
                                    {formatEdge(awayEdge)}
                                </p>
                            </div>
                        </div>

                        {/* Home Team */}
                        <div className="text-center">
                            <img
                                src={logo(game.home_team_id)}
                                alt=""
                                className="w-10 h-10 mx-auto mb-1"
                                onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }}
                            />
                            <p className="font-bold text-[1.2rem]">
                                {game.home}
                            </p>

                            <div className="mt-1">
                                <p className="text-[#888] text-[.8rem]">
                                    MODEL
                                </p>
                                <p className="font-bold text-[1rem]">
                                    {pct(game.home_prediction)}
                                </p>
                            </div>

                            <div className="mt-1">
                                <p className="text-[#888] text-[.8rem]">
                                    POLYMARKET
                                </p>
                                <p className="font-bold text-[1rem]">
                                    {pct(game.home_polymarket)}
                                </p>
                            </div>

                            <div className="mt-1">
                                <p className="text-[#888] text-[.8rem]">
                                    EDGE
                                </p>
                                <p className={`font-bold text-[1rem] ${edgeStyle(homeEdge)}`}>
                                    {formatEdge(homeEdge)}
                                </p>
                            </div>
                        </div>

                    </div>
                </div>
            );
        })}

    </div>
  )
}


