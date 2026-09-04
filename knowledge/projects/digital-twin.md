---
title: Digital twin
kind: project
period: 2026-09 to present
tags: [ai-agents, portfolio, openai, python]
public: true
---

## What it is

A conversational agent that represents Adam on adambuilds.ai. Visitors ask about his career, background, skills, and projects, and the twin answers in his voice from a curated, reviewed knowledge base. This is the agent you are talking to.

## Why

It is the first project in the adambuilds.ai portfolio. It shows agent design end to end: tool use, a knowledge base built from Adam's own narration, evals that catch invention and drift, and the security thinking behind what an agent should and should not know.

## How it works

The twin's knowledge is a set of markdown files, each reviewed by Adam. They are loaded whole into the system prompt, so the agent always has the full picture. Two tools let it record a visitor's email for follow-up and log questions it could not answer, so gaps in the knowledge get filled over time. A suite of evals checks facts, boundaries, and voice against the live model.

## Stack

Python and the OpenAI API, with a terminal harness for local development. A FastAPI service and a custom web front end on adambuilds.ai are the next steps.

## Status

In development, September 2026. The source will be public on GitHub at adamlittleusa/DigitalTwin once it is ready to deploy.
