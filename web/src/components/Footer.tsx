import { Mail, MapPin, Phone } from "lucide-react";

const COMPANY_LINKS = [
  "About Us",
  "Insights & Blog",
  "Careers",
  "Social Givebacks",
  "Solutions",
  "Services",
  "Privacy Policy",
];

const PRODUCT_LINKS = ["YottaBuilder.ai", "SafeChief"];

const ADDRESSES = [
  "4101 Cox Rd, Suite 340, Glen Allen, VA 23060",
  "Suite 670-3300 Bloor Street West, Toronto, Ontario, M8X 2X2",
  "The Business Park, Kondapur, Hyderabad, India 500084",
  "Cra 39 #5a-95, Ofc# 709 Edificio Avantgarde, Medellín, Colombia 050021",
];

export function Footer() {
  return (
    <footer className="relative z-10 mt-10 w-full border-t border-white/25 dark:border-white/10 bg-[#0b1021]/92 dark:bg-[#070b18]/92 backdrop-blur-xl text-zinc-200 overflow-hidden">
      {/* Subtle geometric circuit-trace watermark matching brand footer */}
      <svg
        aria-hidden="true"
        viewBox="0 0 600 220"
        className="pointer-events-none absolute left-0 bottom-10 w-[520px] max-w-full opacity-[0.10] text-sky-400"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
      >
        <path d="M0 180 H110 L145 145 H240 M40 210 H160 L195 175 H310 L345 140 H440 M90 210 L125 175 V110 L160 75 H250" />
        <circle cx="240" cy="145" r="3" fill="currentColor" />
        <circle cx="440" cy="140" r="3" fill="currentColor" />
        <circle cx="250" cy="75" r="3" fill="currentColor" />
      </svg>

      <div className="relative max-w-[1560px] mx-auto px-6 py-11 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-8">
        {/* Brand Column */}
        <div className="lg:col-span-3 space-y-4">
          <a
            href="https://stg.yottaflex.ai"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2.5 group"
          >
            <img
              src="/yottaflex-logo.webp"
              alt="YottaFlex Logo"
              className="w-8 h-8 object-contain brightness-0 invert transition-transform duration-300 group-hover:scale-105"
            />
            <span className="text-xl font-bold tracking-tight text-white">YottaFlex</span>
          </a>
          <p className="text-xs leading-relaxed text-zinc-300/90 max-w-[230px]">
            Your trusted partner in AI innovation, driving growth and efficiency for companies worldwide.
          </p>
        </div>

        {/* Company */}
        <div className="lg:col-span-2 space-y-3">
          <h4 className="text-sm font-semibold text-emerald-400 tracking-wide">Company</h4>
          <ul className="space-y-2 text-xs text-zinc-300">
            {COMPANY_LINKS.map((label) => (
              <li key={label}>
                <a
                  href="https://stg.yottaflex.ai"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2.5 hover:text-white transition"
                >
                  <span className="w-1.5 h-1.5 rounded-[1px] bg-emerald-400 shrink-0" />
                  <span>{label}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>

        {/* Our Products */}
        <div className="lg:col-span-2 space-y-3">
          <h4 className="text-sm font-semibold text-emerald-400 tracking-wide">Our Products</h4>
          <ul className="space-y-2 text-xs text-zinc-300">
            {PRODUCT_LINKS.map((label) => (
              <li key={label}>
                <a
                  href="https://stg.yottaflex.ai"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2.5 hover:text-white transition"
                >
                  <span className="w-1.5 h-1.5 rounded-[1px] bg-emerald-400 shrink-0" />
                  <span>{label}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>

        {/* Contact Us */}
        <div className="lg:col-span-2 space-y-3">
          <h4 className="text-sm font-semibold text-emerald-400 tracking-wide">Contact Us</h4>
          <div className="space-y-2.5 text-xs text-zinc-300">
            <a
              href="tel:+18047817090"
              className="flex items-center gap-2.5 hover:text-white transition"
            >
              <Phone className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span className="ios-num">+1 (804) 781-7090</span>
            </a>
            <a
              href="mailto:contactus@stg.yottaflex.ai"
              className="flex items-center gap-2.5 hover:text-white transition break-all"
            >
              <Mail className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span>contactus@stg.yottaflex.ai</span>
            </a>
            <div className="pt-1.5 flex items-center gap-2.5">
              <a
                href="https://www.linkedin.com"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="YottaFlex LinkedIn"
                className="w-7 h-7 rounded-full bg-emerald-400 hover:bg-emerald-300 text-[#090e1d] font-bold text-xs flex items-center justify-center transition"
              >
                in
              </a>
              <a
                href="https://www.facebook.com"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="YottaFlex Facebook"
                className="w-7 h-7 rounded-full bg-emerald-400 hover:bg-emerald-300 text-[#090e1d] font-bold text-xs flex items-center justify-center transition"
              >
                f
              </a>
            </div>
          </div>
        </div>

        {/* Our Addresses */}
        <div className="lg:col-span-3 space-y-3">
          <h4 className="text-sm font-semibold text-emerald-400 tracking-wide">Our Addresses</h4>
          <ul className="space-y-2.5 text-xs text-zinc-300 leading-relaxed">
            {ADDRESSES.map((addr) => (
              <li key={addr} className="flex items-start gap-2.5">
                <MapPin className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                <span>{addr}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Bottom Copyright Strip */}
      <div className="border-t border-white/[0.07] bg-[#050814]/95 py-3.5 px-6 text-center text-[11.5px] text-zinc-400">
        Copyright &copy; 2026 Yottaflex.ai Inc All Rights Reserved.
      </div>
    </footer>
  );
}
