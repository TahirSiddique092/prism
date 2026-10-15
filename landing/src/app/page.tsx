import Nav from "../components/Nav";
import Hero from "../components/Hero";
import Features from "../components/Features";
import Architecture from "../components/Architecture";
import RunIt from "../components/RunIt";
import Footer from "../components/Footer";

export default function Home() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <Features />
        <Architecture />
        <RunIt />
      </main>
      <Footer />
    </>
  );
}
