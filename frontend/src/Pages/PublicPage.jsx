import flamingBaseball from '../../assests/Flaming_Baseball_logo.png'
import screenshot from '../../assests/ScreenShot_10_1_2026.png'
import website_background from '../../assests/website_background.png'

import { Link } from "react-router-dom";

const steps = [
    {
        title: "Collect",
        text: "Every day, the system pulls game data, starting pitchers, and results from the MLB StatsAPI, built on five seasons of historical games.",
    },
    {
        title: "Predict",
        text: "A machine learning model turns team and pitcher stats into a win probability for every game.",
    },
    {
        title: "Compare",
        text: "Each prediction is matched against live Polymarket odds to show where the model and the market disagree.",
    },
    {
        title: "Update",
        text: "Predictions refresh hourly as pitchers are announced, and live games update with the current inning.",
    },
];

const stats = [
    {
        value: "56.5%",
        label: "Accuracy",
        text: "Picks the winner in 56.5% of games it hasn't seen before.",
    },
    {
        value: "52.8%",
        label: "Baseline",
        text: "Accuracy from always picking the home team. The model beats it by 3.7 points.",
    },
    {
        value: "0.585",
        label: "AUC",
        text: "How well the model ranks winners above losers. 0.5 is a coin flip; 1.0 is perfect.",
    },
];

export function PublicPage(){


    return(
         <div className="bg-[#030d1f] min-h-screen">

            {/* Hero: the only section with the background image */}
            <section className="relative isolate overflow-hidden min-h-screen">
                <img
                    src={website_background}
                    alt=""
                    className="absolute inset-0 h-full w-full -z-20 object-cover"
                />
                {/* Fade the image into the solid color below */}
                <div className="absolute inset-x-0 bottom-0 h-40 -z-10 bg-[linear-gradient(to_bottom,transparent,#030d1f)]" />

                <div className="bg-[#000f26] flex justify-center py-1 border-3 border-[#2c3442]">
                    <img src={flamingBaseball} alt="MLB" className="w-13 h-13" />
                </div>

                <div className="flex justify-center px-[6vw] md:px-[10vw] pt-[3.5vh]">
                    <Link
                        to="/MLB"
                        className="px-10 py-5 min-h-[44px] rounded-md font-bold uppercase tracking-wide 
                                text-[#041129] text-[1.2rem] bg-[#7FB2FF] border-2 border-[#adc3ed]
                                hover:bg-[#adc3ed] active:scale-95 transition
                                focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                    >
                        Check it out
                    </Link>
                </div>

                <div className="flex flex-col md:flex-row items-center md:justify-center gap-8 md:gap-[5vw] px-[6vw] md:px-[10vw] py-[5vh]">
                    <img
                        src={screenshot}
                        alt="Screenshot of the MLB predictions app"
                        className="border-[#232b3b] border-[.25rem] outline-2 outline-[#adc3ed] w-[60vw] max-w-[14rem] md:max-w-[12rem] shrink-0"
                    />
                    <div className="flex flex-col gap-3 min-w-0 text-center md:text-left order-first md:order-none">
                        <h1 className="text-white font-extrabold uppercase tracking-tight leading-none text-[clamp(2.5rem,8vw,5rem)]">
                            Data-Driven
                            <span className="block text-[#7FB2FF]">MLB Picks</span>
                        </h1>
                        <p className="text-[#adc3ed] text-[clamp(1.05rem,2.5vw,1.25rem)] max-w-[28rem] mx-auto md:mx-0">
                            Every pick backed by stats, trends and matchup data.
                        </p>
                    </div>
                </div>
            </section>

            {/* Scroll-down arrow */}
            <button
                type="button"
                onClick={() => document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" })}
                aria-label="Scroll down to learn more"
                className="absolute bottom-6 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1
                        text-[#adc3ed] hover:text-white transition
                        focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white rounded-md"
            >
                <span className="text-xs uppercase tracking-widest">Learn more</span>
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="w-8 h-8 motion-safe:animate-bounce"
                >
                    <polyline points="6 9 12 15 18 9" />
                </svg>
            </button>

             {/* About: solid background */}
            <section id="how-it-works" className="px-[6vw] md:px-[10vw] py-20">
                <div className="max-w-5xl mx-auto">
                    <h2 className="text-white font-extrabold uppercase tracking-tight leading-none text-[clamp(2rem,5vw,3.5rem)] mb-4">
                        How It <span className="text-[#7FB2FF]">Works</span>
                    </h2>
                    <p className="text-[#adc3ed] text-[clamp(1.05rem,2vw,1.2rem)] max-w-2xl mb-12">
                        A machine learning pipeline that turns five seasons of MLB data into daily win predictions.
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                        {steps.map((step, i) => (
                            <div
                                key={step.title}
                                className="bg-[#000f26] border-2 border-[#2c3442] rounded-md p-6"
                            >
                                <span className="text-[#7FB2FF] font-bold text-sm">0{i + 1}</span>
                                <h3 className="text-white font-bold uppercase text-xl mt-1 mb-2">{step.title}</h3>
                                <p className="text-[#adc3ed] leading-relaxed">{step.text}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* The Model: stats and explanations */}
            <section className="px-[6vw] md:px-[10vw] pb-20">
                <div className="max-w-5xl mx-auto">
                    <h2 className="text-white font-extrabold uppercase tracking-tight leading-none text-[clamp(2rem,5vw,3.5rem)] mb-4">
                        The <span className="text-[#7FB2FF]">Model</span>
                    </h2>
                    <p className="text-[#adc3ed] text-[clamp(1.05rem,2vw,1.2rem)] max-w-2xl mb-12">
                        Baseball is one of the hardest sports to predict. Even the best teams lose about
                        40% of their games, so small edges over a coin flip are what matter.
                    </p>

                    {/* Stat cards */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-12">
                        {stats.map((stat) => (
                            <div
                                key={stat.label}
                                className="bg-[#000f26] border-2 border-[#2c3442] rounded-md p-6 text-center"
                            >
                                <p className="text-[#7FB2FF] font-extrabold text-[clamp(2.25rem,5vw,3rem)] leading-none">
                                    {stat.value}
                                </p>
                                <p className="text-white font-bold uppercase text-sm tracking-wide mt-3 mb-2">
                                    {stat.label}
                                </p>
                                <p className="text-[#adc3ed] text-sm leading-relaxed">{stat.text}</p>
                            </div>
                        ))}
                    </div>

                    {/* Explanations */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="bg-[#000f26] border-2 border-[#2c3442] rounded-md p-6">
                            <h3 className="text-white font-bold uppercase text-xl mb-2">Pre-Game Predictions</h3>
                            <p className="text-[#adc3ed] leading-relaxed">
                                Every prediction is made before first pitch, using only information available
                                before the game: team performance, recent trends, and the announced starting
                                pitchers. Predictions don't change once a game starts, even if one team jumps
                                out to a big lead. The live inning is shown for reference only.
                            </p>
                        </div>

                        <div className="bg-[#000f26] border-2 border-[#2c3442] rounded-md p-6">
                            <h3 className="text-white font-bold uppercase text-xl mb-2">What Edge Means</h3>
                            <p className="text-[#adc3ed] leading-relaxed mb-3">
                                Edge is the difference between the model's win probability and the
                                Polymarket price, in percentage points. A positive edge means the model rates a
                                team higher than the market does.
                            </p>
                            <p className="text-[#adc3ed] leading-relaxed">
                                For example, if the model gives the Braves a 55.4% chance and Polymarket prices
                                them at 50.5%, the edge is <span className="text-[#4ade80] font-bold">+4.9</span>.
                                Edge is only meaningful before first pitch, since market odds move during the
                                game while the model's prediction stays fixed.
                            </p>
                        </div>
                    </div>
                </div>
            </section>
        </div>


    )
}