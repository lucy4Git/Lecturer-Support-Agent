export default function OfflinePage() {
  return (
    <main className="offline-page">
      <section>
        <span className="eyebrow">Connection unavailable</span>
        <h1>You are offline</h1>
        <p>Your saved browser shell is available, but secure conversations, institutional files, and AI generation require a connection.</p>
        <a href="/">Try again</a>
      </section>
    </main>
  );
}
