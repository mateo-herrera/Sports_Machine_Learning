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




    //Find the most likely winners for today by comparing model and prediction markets
    const MIN_PROB = 57.5;  // model must give the team at least 58%
    const MAX_DIFF = 4;   // model and Polymarket within 4 points

    const likelyWinners = todayGames
    .filter((g) => !g.is_final)
    .flatMap((g) => [
        { game: g, team: g.away, teamId: g.away_team_id, model: g.away_prediction * 100, market: g.away_polymarket * 100 },
        { game: g, team: g.home, teamId: g.home_team_id, model: g.home_prediction * 100, market: g.home_polymarket * 100 },
    ])
    .filter((p) =>
        Number.isFinite(p.model) &&
        Number.isFinite(p.market) &&
        p.model >= MIN_PROB &&
        Math.abs(p.model - p.market) <= MAX_DIFF
    )
    .sort((a, b) => b.model - a.model)
    .slice(0, 3);

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

        {/* Todays Games Most Likely Winners */}
        <div className="w-[95%] mx-auto mb-1 mt-3 box-border rounded-lg border-2 border-[#2c3442] bg-[#050c14] text-white">
            <div className="flex justify-between px-4 py-2">
                <span className='text-[1rem] font-bold'>Today's Most Likely Winners</span>
                <span className='text-[.9rem] font-bold text-[#c7c7c7]'>{today_date}</span>
            </div>
        </div>
        {likelyWinners.length > 0 && (
        <div className="w-[95%] mx-auto">
            <div className="flex flex-col">
            {likelyWinners.map((p, i) => {
                const cardBG = i % 2 === 0 ? 'bg-[#232b38]' : 'bg-[#151c26]';
                const logoBG = i % 2 === 0 ? 'bg-[#333942]' : 'bg-[#2e3c52]';
                
                return (
                    <div
                    key={`${p.game.game_id}-${p.team}`}
                    className={`w-[90%] ${cardBG} border-2 border-[#2c3442] rounded-lg px-1 py-[.1rem] text-white mx-auto mt-1 flex items-center justify-between`}
                    >
                    <div className="flex items-center gap-3 min-w-0">
                        <div className={`w-9 h-9 shrink-0 border-2 border-[#404f66] ${logoBG} rounded-md p-[.3rem] flex items-center justify-center`}>
                            <img
                                src={logo(p.teamId)}
                                alt=""
                                className="w-full h-full object-contain"
                                onError={(e) => { e.currentTarget.parentElement.style.visibility = 'hidden'; }}
                            />
                        </div>
                        <p className="font-bold text-[.9rem] truncate">{p.team}</p>
                    </div>
                    <div className="flex text-[.8rem] gap-3  shrink-0">
                        <p className="w-14 text-[#c7c7c7] notflex">
                        Model: <span className="block text-white font-bold">{p.model.toFixed(1)}%</span>
                        </p>
                        <p className="w-14 text-[#c7c7c7]">
                        Market: <span className="block text-white font-bold">{p.market.toFixed(1)}%</span>
                        </p>
                        <p className="w-14 text-[#c7c7c7] ">
                        Time: <span className="block text-white font-bold">{p.game.time}</span>
                        </p>
                    </div>
                    </div>
            );
            })}
            </div>
        </div>
        )}
        {/* Todays Games */}
        <div className="w-[95%] mx-auto mb-1 mt-3 box-border rounded-lg border-2 border-[#2c3442] bg-[#050c14] text-white">
            <div className="flex justify-between px-4 py-2">
                <span className='text-[1rem] font-bold'>Today's Games</span>
                <span className='text-[.9rem] font-bold text-[#c7c7c7]'>{today_date}</span>
            </div>
        </div>

        {todayGames.map((game, i) => {
            const awayEdge = edge(game.away_prediction, game.away_polymarket);
            const homeEdge = edge(game.home_prediction, game.home_polymarket);
            const cardBG = i % 2 === 0 ? 'bg-[#232b38]' : 'bg-[#151c26]';
            const logoBG = i % 2 === 0 ? 'bg-[#333942]' : 'bg-[#2e3c52]';

            return (
                <div
                    key={game.game_id}
                    className={`w-[80%] ${cardBG} border-2 border-[#2c3442] rounded-lg p-1 text-white mx-auto mt-2 mb-2`}
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
                            <div className={`w-12 h-12 mx-auto mb-1 border-2 border-[#404f66] ${logoBG} rounded-md p-1 flex items-center justify-center`}>
                                <img
                                    src={logo(game.away_team_id)}
                                    alt=""
                                    className="w-full h-full object-contain"
                                    onError={(e) => { e.currentTarget.parentElement.style.visibility = 'hidden'; }}
                                />
                            </div>
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
                            <div className={`w-12 h-12 mx-auto mb-1 border-2 border-[#404f66] ${logoBG} rounded-md p-1 flex items-center justify-center`}>
                                <img
                                    src={logo(game.home_team_id)}
                                    alt=""
                                    className="w-full h-full object-contain"
                                    onError={(e) => { e.currentTarget.parentElement.style.visibility = 'hidden'; }}
                                />
                            </div>
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
        <div className="w-[95%] mx-auto mb-1 mt-3 box-border rounded-lg border-2 border-[#2c3442] bg-[#050c14] text-white">
            <div className="flex justify-between px-4 py-2">
                <span className='text-[1rem] font-bold'>Tomorrows's Games</span>
                <span className='text-[.9rem] font-bold  text-[#c7c7c7]'>{tomorrows_date}</span>
            </div>
        </div>

        {/* Maps Tomorrows games to cards */}
        {tomorrowGames.map((game, i) => {
            const awayEdge = edge(game.away_prediction, game.away_polymarket);
            const homeEdge = edge(game.home_prediction, game.home_polymarket);
            const cardBG = i % 2 === 0 ? 'bg-[#232b38]' : 'bg-[#151c26]';
            const logoBG = i % 2 === 0 ? 'bg-[#333942]' : 'bg-[#2e3c52]';

            return (
                <div
                    key={game.game_id}
                    className={`w-[80%] ${cardBG} border-2 border-[#2c3442] rounded-lg p-1 text-white mx-auto mt-2 mb-2`}
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
                            <div className={`w-12 h-12 mx-auto mb-1 border-2 border-[#404f66] ${logoBG} rounded-md p-1 flex items-center justify-center`}>
                                <img
                                    src={logo(game.away_team_id)}
                                    alt=""
                                    className="w-full h-full object-contain"
                                    onError={(e) => { e.currentTarget.parentElement.style.visibility = 'hidden'; }}
                                />
                            </div>
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
                            <div className={`w-12 h-12 mx-auto mb-1 border-2 border-[#404f66] ${logoBG} rounded-md p-1 flex items-center justify-center`}>
                                <img
                                    src={logo(game.home_team_id)}
                                    alt=""
                                    className="w-full h-full object-contain"
                                    onError={(e) => { e.currentTarget.parentElement.style.visibility = 'hidden'; }}
                                />
                            </div>
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


