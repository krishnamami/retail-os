/**
 * The story, told once, in the order a buyer needs it.
 *
 *   what breaks today  ->  why it breaks  ->  what proliferation costs  ->
 *   what governs the answer  ->  what it is built on  ->  see it live
 *
 * The landing page states no governed outcome. Every number it quotes is a
 * count from the deployed corpus, and the sections that quote them say so.
 */
import Nav from "../components/lp/Nav";
import Hero from "../components/lp/Hero";
import Bottlenecks from "../components/lp/Bottlenecks";
import Proliferation from "../components/lp/Proliferation";
import WhyTable from "../components/lp/WhyTable";
import Governance from "../components/lp/Governance";
import Architecture from "../components/lp/Architecture";
import CTASection from "../components/lp/CTASection";
import Footer from "../components/lp/Footer";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      <Nav />
      <main>
        <Hero />
        <Bottlenecks />
        <Proliferation />
        <WhyTable />
        <Governance />
        <Architecture />
        <CTASection />
      </main>
      <Footer />
    </div>
  );
}
