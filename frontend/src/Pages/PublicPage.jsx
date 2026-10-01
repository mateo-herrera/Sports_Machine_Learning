import flamingBaseball from '../../assests/Flaming_Baseball_logo.png'
import screenshot from '../../assests/ScreenShot_10_1_2026.png'
import website_background from '../../assests/website_background.png'

import { Link } from "react-router-dom";

export function PublicPage(){


    return(
        <div className="bg-[#030d1f] isolate min-h-screen">
            <img src={website_background} alt='Web Background' className='fixed inset-0 h-full w-full -z-10 object-cover'/>

            <div className="bg-[#000f26] flex justify-center py-1 border-3 border-[#2c3442]">
                <img src={flamingBaseball} alt="MLB" className="w-13 h-13" />
            </div>

            <div className="flex justify-center px-[6vw] md:px-[10vw] pt-[3.5vh]">
                <Link
                    to="/MLB"
                    className="px-6 py-2.5 min-h-[44px] rounded-md font-bold uppercase tracking-wide text-sm
                            text-[#000f26] bg-[#7FB2FF] border-2 border-[#adc3ed]
                            hover:bg-[#adc3ed] active:scale-95 transition
                            focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                >
                    Check it out
                </Link>
            </div>

            <div className="flex flex-row items-center md:justify-center gap-[4vw] md:gap-[5vw] px-[6vw] md:px-[10vw] py-[5vh]">                
                <img
                    src={screenshot}
                    alt="Screenshot"
                    className="border-[#232b3b] border-[.25rem] outline-2 outline-[#adc3ed] w-[45vw] max-w-[12rem] shrink-0"
                />
                <div className="flex flex-col gap-3 min-w-0">
                    <h1 className="text-white font-extrabold uppercase tracking-tight leading-none text-[clamp(1.5rem,6vw,5rem)]">
                        Data-Driven
                        <span className="block text-[#7FB2FF]">MLB Picks</span>
                    </h1>
                    <p className="text-[#adc3ed] text-[clamp(0.8rem,1.6vw,1.25rem)] max-w-[28rem]">
                        Every pick backed by stats, trends and matchup data.
                    </p>
                </div>
            </div>


        </div>


    )
}