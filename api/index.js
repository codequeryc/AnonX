const axios = require("axios");
const { parseStringPromise } = require("xml2js");

module.exports = async (req, res) => {
  const BOT_TOKEN = process.env.BOT_TOKEN;
  const BLOG_URL = process.env.BLOG_URL;
  const TELEGRAM_API = `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`;

  // ✅ Show "Bot is live" on GET request
  if (req.method === "GET") {
    return res.status(200).send("🤖 Movie Bot is live on Vercel!");
  }

  // ✅ Telegram POST webhook
  if (req.method === "POST") {
    const data = req.body;

    if (!data.message || !data.message.text) {
      return res.status(200).json({ ok: true });
    }

    const chatId = data.message.chat.id;
    const text = data.message.text.trim();
    let reply = "";

    if (text === "/start") {
      reply = "👋 Welcome to MovieBot!\nSend a movie name to get the download link.";
    } else if (text === "/help") {
      reply = "ℹ️ Just send a movie name. Example: `Jawan 2023`";
    } else {
      const searchUrl = `${BLOG_URL}/feeds/posts/default?q=${encodeURIComponent(text)}&alt=rss`;
      try {
        const response = await axios.get(searchUrl);
        const parsed = await parseStringPromise(response.data);
        const items = parsed.rss.channel[0].item;

        if (items && items.length > 0) {
          const entry = items[0];
          const title = entry.title[0];
          const link = entry.link[0];
          reply = `🎬 *${title}*\n🔗 [Download Now](${link})`;
        } else {
          reply = "🚫 Movie not found.";
        }
      } catch (err) {
        console.error("Feed Error:", err.message);
        reply = "❌ Error fetching from Blogger feed.";
      }
    }

    await axios.post(TELEGRAM_API, {
      chat_id: chatId,
      text: reply,
      parse_mode: "Markdown",
      disable_web_page_preview: false
    });

    return res.status(200).json({ ok: true });
  }

  // ❌ Method not allowed
  res.status(405).send("Method Not Allowed");
};
