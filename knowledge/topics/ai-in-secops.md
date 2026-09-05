---
title: AI in security operations looks bespoke; the outcomes are not
kind: topic
tags: [ai-security, secops, product, opinion]
public: true
reviewed: 2026-09-05
---

Adam's core lesson from leading AI-driven security response product work at Corelight.

Applying AI and automation to security operations looks complicated and bespoke to every customer, and at one level it is: every environment needs its own contextualization. But the goal customers are trying to reach is mostly the same across all of them. Treating each customer segment, or each delivery model, as a completely separate product with separate outcomes is a mistake that is easy to make in the middle of the data and obvious only in hindsight. The better shape is one set of outcomes delivered in distinct flavors: at Corelight that meant a SaaS approach and a sensor-only approach to the same thing, for customers who can adopt SaaS and the regulated majority who cannot.

The way to get there is the voice of the customer. Adam built a design partner program, turned the conversations into a knowledge base of design intention, and used it to reshape the AI product strategy. He describes network detection and response as the often-forgotten third leg of the SecOps stool, alongside SIEM and EDR, and network sensor data as the ground truth of what is happening on a network.

Adam adds two really hard parts of security work in AI. First, to build high-performing, dependable agents you need to build and hold decent evals data, and that is hard for security vendors because it requires the client to trust the vendor up front, before any ROI. Trust is the most essential bottleneck resource for SecOps and agentic workflows. Second, securing AI needs to happen at an abstraction layer above where most people are looking and thinking: security tooling and threat models need to be pointed at the harness around the agent, not just at the agent or the models themselves.
