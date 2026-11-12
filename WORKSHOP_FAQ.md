# Workshop FAQ — AI for the Network Forward Engineer

*Track D1 · Tuesday afternoon (2:00–6:00pm) · AutoCon 6*

Quick answers to questions I get a lot before this kind of workshop. Short version: bring a laptop, a GitHub account (the workshop runs in GitHub Codespaces), an OpenAI account with $5 of credit, and a free Arize AX account — and join `#ac6-ws-d1-ai-for-the-network-forward-engineer` on the Network Automation Forum Slack before workshop day. That's it.

---

**Do I need to install anything beforehand?**

Almost nothing. The whole workshop runs inside a GitHub Codespace — a cloud-based dev environment — so you don't need Docker, Python, or any of the AI tools installed locally. Just a modern browser (Chrome works best) and your laptop's terminal.

---

**I'll need a GitHub account, right?**

Yes. Free tier is fine. Sign up at [github.com](https://github.com) if you don't have one — takes two minutes.

The reason is **GitHub Codespaces**: the whole lab environment (local LLM, network simulator, Python toolchain) runs in a Codespace tied to your GitHub account. No GitHub account, no Codespace, no workshop environment — it's the one account that isn't optional.

---

**Will GitHub Codespaces cost me anything?**

The free tier includes **120 core-hours and 15 GB-month of storage** — way more than a 4-hour workshop needs.

**Heads up though:** if you've already used Codespaces a lot this month for other projects, you might be close to your limit. Two minutes of homework before the workshop:

1. Check your usage at [github.com/settings/billing/summary](https://github.com/settings/billing/summary)
2. Stop any unused Codespaces if you're getting close

If you do hit the limit mid-workshop, paying a small overage (~$0.18/hour for a 4-core machine) keeps you running. Or use a different GitHub account.

---

**One setting to change before workshop day: the idle timeout**

Codespaces stop themselves after **30 minutes without activity** — which is exactly the length of our afternoon break. A stopped Codespace resumes in seconds and keeps your files, but the things you started by hand (the local LLM server, the router topology, the Streamlit app) have to be restarted. Save yourself the hassle: go to [github.com/settings/codespaces](https://github.com/settings/codespaces), find **Default idle timeout**, and set it to **240 minutes** (the maximum). It only applies to Codespaces created *after* you change it, so do it before Tuesday. The cost difference is nil for our purposes — an idle Codespace during a 30-minute break is 2 core-hours.

---

**Do I need GitHub Pro? Is there a "nicer" setup?**

No — the free default works for the entire workshop. But if you have GitHub Pro (or any paid plan that unlocks larger machines), you can opt into a second configuration, *"AutoCon 6 AI Workshop — GitHub Pro (larger machine)"*, that runs on an 8-core / 32 GB machine instead of the free 4-core / 16 GB one. It's noticeably snappier (especially when the network sim and a local LLM run side by side) and adds the **Open WebUI** chat GUI in Lab 1. Pick it by choosing **New with options…** at launch and selecting it from the **Dev container configuration** dropdown. Totally optional — the free default is sufficient.

---

**Which cloud LLM provider do I need an account with?**

**OpenAI.** Sign up at [platform.openai.com](https://platform.openai.com) and add **$5 USD** as prepaid credit before the workshop.

$5 is plenty — you'll likely spend under $0.50 during the lab. Whatever's left doesn't expire and is yours to use for anything else later.

If you can't add credit for some reason, flag it to me at the workshop — I have a backup key for emergencies, but bringing your own is strongly preferred.

---

**What's this Arize AX account for?**

New this year: in Lab 5 we trace and *evaluate* the AI application you build — checking its accuracy and testing for hallucinations — using the Arize AX platform. It's the part of the workshop where you learn to answer "how do I know my AI app is actually right?"

Before the workshop:

1. Sign up for a **free** account at [app.arize.com](https://app.arize.com) (you'll verify your email and set a password).
2. Once you're in, find **Space Settings** and note where your **Space ID** and **API Key** live — you'll copy both into the lab environment on workshop day.

That's it — no credit card, the free tier covers everything we do.

**Will my OpenAI key go into Arize?** Yes, in Lab 5. Arize's prompt playground and its LLM judge call a model on your behalf, and on the free tier that means your provider and your key, stored in your own Arize space (**Settings → AI Providers**). The lab walks you through it. What runs there costs a few cents of your $5 credit, and you can revoke the key at OpenAI whenever you like. *(Updated 12 November: an earlier version of this page said you would not need to do this. The lab changed, and so did this answer.)*

**Already use Arize at work?** Sign up for a fresh personal free account anyway. The labs assume Arize's US region (the default for self-serve signups); a company account may be hosted in the EU region, which needs different endpoints we don't cover. A personal space also keeps workshop data out of your employer's account.

---

**Why OpenAI and not Anthropic, Google, or someone else?**

All of those are excellent. We're using OpenAI mainly for familiarity — most attendees have already used ChatGPT, so account setup is fast and the API mental model is comfortable.

There's a practical reason too: the AI coding assistant bundled into Codespaces (GitHub Copilot) defaults to OpenAI models, so you're already working with one vendor's models in the editor — the labs just use the same family through the API.

The recipes we build are provider-agnostic — once the workshop is over, swapping in Claude, Gemini, or a local model is a one-line change in the LangChain code. (There's a bonus mini-lab for exactly that if you finish early.)

---

**Can I keep working on this after the workshop?**

Yes — with one deadline. Everything we build together is yours to take back to your day job; you should leave with a working AI-augmented networking toolkit — *and* the evaluation harness to prove it works — that you can use Monday morning.

**Heads up:** the workshop repo and the dev container image will be made **private a few days after the workshop**. Two things to do during workshop week, while they're still public:

1. **Fork (or clone) the repo** so you keep the source and your own edits.
2. **Don't delete your Codespace.** A stopped Codespace resumes without re-pulling the image, so it keeps working after the image goes private — but a *new* Codespace (from the original repo or from your fork) won't be able to pull the image anymore. Note that GitHub auto-deletes Codespaces after 30 days of inactivity by default; you can extend that in your Codespaces settings.

The Slack channel stays open for follow-up questions.

---

**How much Python and networking do I need to know?**

- **Python**: intermediate enough to read and edit a script. You don't need to be a developer.
- **Networking**: comfortable with the basics — BGP, OSPF, route tables, what a `show` command output looks like. We're not teaching networking; we're teaching how AI helps with the networking work you already do.

---

**What if I finish a lab early?**

Great — this workshop is built for you. Every lab has a **Going Further** section with real exercises, and there's a `bonus/` folder (MCP, real RAG, a swap to Anthropic Claude, a discussion guide) beyond that — content, not filler. Advanced folks at the last AutoCon finished early; this time there's a deeper trail to keep going on.

---

**What if I get stuck?**

Raise a hand — **Eric Chou** and **Adam Byczkowski** are proctoring in the room. Or post in `#ac6-ws-d1-ai-for-the-network-forward-engineer` on the Network Automation Forum Slack: it's live now, it's the fastest way to share an error message or screenshot during the session, and it's where pre-workshop questions and post-workshop follow-up happen too. Join it before workshop day.

---

**What if my company blocks GitHub, OpenAI, or Arize?**

Best to do this workshop on a personal device via the venue WiFi. Some corporate networks block Codespaces, external AI APIs, or SaaS tools — if yours does, your personal laptop on conference WiFi is the right move.

---

**Anything else I should bring?**

Just curiosity. And maybe a charger.

See you Tuesday afternoon.

— Eric
