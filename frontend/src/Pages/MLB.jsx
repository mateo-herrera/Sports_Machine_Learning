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

    // Date strings in 'YYYY-MM-DD' format to match backend's 'date' field
    function toLocalDateString(d) {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
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

        {/* Maps Todays games to cards */}
        {todayGames.map((game, index) => (
            <div
                key={index}
                className="w-[80%] bg-[#232b38] border-2 border-[#2c3442] rounded-lg p-1 text-white mx-auto mt-2 mb-2"
            >
                <p className="text-[#888] text-[1rem] flex justify-center">
                    {game.time}
                </p>

                <div className="grid grid-cols-2">

                    {/* Away Team */}
                    <div className="text-center border-r border-[#2c3442]">
                        <p className="font-bold text-[1.2rem]">
                            {game.away}
                        </p>

                        <div className="mt-1">
                            <p className="text-[#888] text-[.8rem]">
                                MODEL
                            </p>
                            <p className="font-bold text-[1rem]">
                                {game.away_prediction}
                            </p>
                        </div>

                        <div className="mt-1">
                            <p className="text-[#888] text-[.8rem]">
                                POLYMARKET
                            </p>
                            <p className="font-bold text-[1rem]">
                                {game.away_polymarket}
                            </p>
                        </div>
                    </div>

                    {/* Home Team */}
                    <div className="text-center">
                        <p className="font-bold text-[1.2rem]">
                            {game.home}
                        </p>

                        <div className="mt-1">
                            <p className="text-[#888] text-[.8rem]">
                                MODEL
                            </p>
                            <p className="font-bold text-[1rem]">
                                {game.home_prediction}
                            </p>
                        </div>

                        <div className="mt-1">
                            <p className="text-[#888] text-[.8rem]">
                                POLYMARKET
                            </p>
                            <p className="font-bold text-[1rem]">
                                {game.home_polymarket}
                            </p>
                        </div>
                    </div>

                </div>
            </div>
        ))}
        
        

        {/*Tomorrows Games */}
        <div className="w-[95%] mx-auto mb-1 mt-3 box-border rounded-lg border-2 border-[#2c3442] bg-[#131d2e] text-white">
            <div className="flex justify-between px-4 py-2">
                <span className='text-[1rem] font-bold'>Tomorrows's Games</span>
                <span className='text-[.9rem] font-light text-[#c7c7c7]'>{tomorrows_date}</span>
            </div>
        </div>

        {/* Maps tomorrows games to cards */}
        {tomorrowGames.map((game, index) => (
            <div
                key={index}
                className="w-[80%] bg-[#232b38] border-2 border-[#2c3442] rounded-lg p-1 text-white mx-auto mt-2 mb-2"
            >
                <p className="text-[#888] text-[1rem] flex justify-center">
                    {game.time}
                </p>

                <div className="grid grid-cols-2">

                    {/* Away Team */}
                    <div className="text-center border-r border-[#2c3442]">
                        <p className="font-bold text-[1.2rem]">
                            {game.away}
                        </p>

                        <div className="mt-1">
                            <p className="text-[#888] text-[.8rem]">
                                MODEL
                            </p>
                            <p className="font-bold text-[1rem]">
                                {game.away_prediction}
                            </p>
                        </div>

                        <div className="mt-1">
                            <p className="text-[#888] text-[.8rem]">
                                POLYMARKET
                            </p>
                            <p className="font-bold text-[1rem]">
                                {game.away_polymarket}
                            </p>
                        </div>
                    </div>

                    {/* Home Team */}
                    <div className="text-center">
                        <p className="font-bold text-[1.2rem]">
                            {game.home}
                        </p>

                        <div className="mt-1">
                            <p className="text-[#888] text-[.8rem]">
                                MODEL
                            </p>
                            <p className="font-bold text-[1rem]">
                                {game.home_prediction}
                            </p>
                        </div>

                        <div className="mt-1">
                            <p className="text-[#888] text-[.8rem]">
                                POLYMARKET
                            </p>
                            <p className="font-bold text-[1rem]">
                                {game.home_polymarket}
                            </p>
                        </div>
                    </div>

                </div>
            </div>
        ))}

    </div>
  )
}


