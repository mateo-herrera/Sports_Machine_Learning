import { useEffect, useState } from "react";

import snail from '../../assests/snail.png'

export default function DelayNotice() {
  const [open, setOpen] = useState(true)

  function close() {
    setOpen(false)
  }

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && close();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={close}
      role="dialog"
      aria-modal="true"
      aria-labelledby="notice-title"
    >
      <div
        className="w-full max-w-sm rounded-md border-2 border-[#2c3442] bg-[#000f26] p-6 text-center shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <img
          src={snail}
          alt=""
          className="mx-auto mb-3 h-18 w-18 object-contain"
        />
        <h2
          id="notice-title"
          className="mb-2 text-xl font-extrabold uppercase tracking-tight text-white"
        >
          Heads <span className="text-[#7FB2FF]">Up</span>
        </h2>
        <p className="mb-5 leading-relaxed text-[#adc3ed]">
          This site is hosted on a free tier, so the server may take up to a
          minute to start up. Expect some delays when loading predictions.
          Thanks for your patience!
        </p>
        <button
          type="button"
          onClick={close}
          className="min-h-[44px] rounded-md border-2 border-[#adc3ed] bg-[#7FB2FF] px-8 py-2
                     font-bold uppercase tracking-wide text-[#041129]
                     transition hover:bg-[#adc3ed] active:scale-95
                     focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white"
        >
          Got it
        </button>
      </div>
    </div>
  );
}