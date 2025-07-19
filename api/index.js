const fetch = require("node-fetch");

module.exports = async (req, res) => {
  if (req.method === "GET") {
    return res.status(200).send("🤖 Movie Bot is Live");
  }

  if (req.method === "POST") {
    const body = req.body;

    if (!body.message || !body.message.text) {
      return res.status(200).send("No message");
    }

    const chatId = body.message.chat.id;
    const text = body.message.text;
    const command = text.trim().toLowerCase();

    if (command.startsWith("/movie")) {
      const query = command.replace("/movie", "").trim();
      const data = await searchMovie(query);
      const message = data || `❌ Movie "${query}" not found.`;
      await sendMessage(chatId, message);
    } else {
      await sendMessage(chatId, "Send `/movie movie-name` to search.");
    }

    return res.status(200).send("OK");
  }
};

// Send message to user
async function sendMessage(chatId, text) {
  const url = `https://api.telegram.org/bot${process.env.BOT_TOKEN}/sendMessage`;
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
}

// Search movie from Blogger feed
async function searchMovie(query) {
  const url = process.env.BLOG_URL;
  const res = await fetch(url);
  const json = await res.json();
  const entries = json.feed.entry;

  if (!entries) return null;

  for (let post of entries) {
    const title = post.title.$t.toLowerCase();
    if (title.includes(query.toLowerCase())) {
      const link = post.link.find(l => l.rel === "alternate").href;
      return `🎬 *${post.title.$t}*\n🔗 ${link}`;
    }
  }

  return null;
}
