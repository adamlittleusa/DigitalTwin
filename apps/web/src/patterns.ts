export const PATTERN_KEYS = [
  "prompt-chaining",
  "routing",
  "parallelization",
  "orchestrator-workers",
  "evaluator-optimizer",
  "autonomous-agent",
] as const;

export type PatternKey = (typeof PATTERN_KEYS)[number];

export type Pattern = {
  key: PatternKey;
  name: string;
  oneLine: string;
  long: string[];
};

// The `long` paragraphs are drafts in Adam's voice, grounded in the
// definitions from Anthropic's "Building effective agents". Adam reviews
// them before merge.
export const PATTERNS: Record<PatternKey, Pattern> = {
  "prompt-chaining": {
    key: "prompt-chaining",
    name: "Prompt chaining",
    oneLine:
      "Steps in sequence, each one's output the next one's input, with checks between.",
    long: [
      "Prompt chaining breaks a task into a fixed sequence of model calls. Each call does one small thing well and passes its output forward, and between steps I can put a programmatic check, a gate, that confirms the work is still on track before the next call spends tokens on it.",
      "I reach for it when a task decomposes cleanly into steps I can name in advance. Write the outline, then the draft, then the translation. Extract the fields, then validate them, then format the result. If I can draw the steps on a whiteboard without any branching, a chain is usually the right shape.",
      "The cost is latency. Three calls in a row take three times as long as one, and every gate adds code I have to maintain. The trade is worth it when each step gets measurably better because it only has to do one thing, and when a failure caught at step two is cheaper than a bad answer at the end.",
      "Where it goes wrong is when the steps are not really independent. If step three needs to reconsider what step one decided, the chain has no way to go back, and I end up either stuffing more context into every prompt or bolting on retries that turn a simple pipeline into an unhappy loop.",
      "In a good chain I look for gates that check something concrete, a schema, a word count, a required field, rather than asking another model whether the output looks fine. I also want each step to be testable on its own, with fixed inputs, so a regression tells me exactly which link broke.",
    ],
  },
  routing: {
    key: "routing",
    name: "Routing",
    oneLine: "Classify the input, send it to the specialist path that fits.",
    long: [
      "Routing puts a classifier in front of a set of specialized handlers. The first call decides what kind of input this is, and the input goes to a prompt, a model, or a whole workflow built for that kind. Nothing downstream has to cope with every case at once.",
      "I reach for it when the inputs fall into distinct categories that want different handling and a single prompt is getting worse at all of them as it tries to cover each. Support questions that split into refunds, technical problems, and general inquiries are the textbook example. Sending easy questions to a smaller, faster model and hard ones to a larger one is another.",
      "The cost is the classification step itself, both the extra latency and the fact that it can be wrong. A misroute is often worse than a mediocre generic answer, because the specialist path was never built to notice it has the wrong kind of input.",
      "It goes wrong when the categories are fuzzy or the routing rules drift from what the handlers actually expect. I have seen routers with twelve categories where nobody could say what separated four of them. That is not routing; that is a lookup table nobody maintains.",
      "In a good router I look for a small set of categories with a clear default, a classifier I can evaluate against labeled examples, and handlers that fail loudly when the input does not fit. If I cannot measure the routing accuracy separately from the answer quality, I cannot tell which half is broken.",
    ],
  },
  parallelization: {
    key: "parallelization",
    name: "Parallelization",
    oneLine: "Run independent pieces at once, then combine or vote.",
    long: [
      "Parallelization runs several model calls at the same time and combines what comes back. There are two flavors. Sectioning splits a task into independent pieces and stitches the results together. Voting runs the same task several times and takes the consensus, or the strictest answer, depending on what the task needs.",
      "I reach for sectioning when the pieces genuinely do not depend on each other, such as screening a request for policy problems in one call while answering it in another. I reach for voting when I care more about confidence than speed, such as reviewing code for vulnerabilities where three independent passes catch more than one careful one.",
      "The cost is tokens. Five parallel calls are five calls, and the combine step is one more. It is fast in wall-clock time, which is why it is tempting, but it is not cheap, and the combining logic has to handle disagreement, partial failure, and outputs that do not line up the way I expected.",
      "It goes wrong when the pieces were not as independent as I thought. If the summary of section two needs to know what section one said, running them at once produces a result that reads like it was written by two people who never met. Voting goes wrong when the voters share a bias, because agreement then means nothing.",
      "In a good one I look for a split that I can justify in one sentence, a combine step that is deterministic where possible, and a clear rule for what happens when one branch fails. I also want to see the voting threshold written down, and a reason for it.",
    ],
  },
  "orchestrator-workers": {
    key: "orchestrator-workers",
    name: "Orchestrator-workers",
    oneLine:
      "One agent breaks the task down and hands parts to workers, then assembles.",
    long: [
      "In orchestrator-workers a central model reads the task, decides what subtasks it needs, hands each one to a worker, and assembles the results. The difference from parallelization is that the subtasks are not known in advance. The orchestrator works them out from the input, which is what makes this a pattern for open-ended problems.",
      "I reach for it when I cannot predict the shape of the work. A change that touches an unknown number of files, or a research question where the sources to consult depend on what the first pass turns up, both want an orchestrator. If I could list the subtasks ahead of time, I would use a chain or a parallel fan-out instead.",
      "The cost is that the orchestrator is now a planner, and planning is where models are least reliable. It can over-decompose, under-decompose, or hand a worker a subtask with too little context to do it well. Every worker call is a separate context window, so the orchestrator has to be explicit about what each one needs to know.",
      "It goes wrong when the orchestrator and the workers disagree about what done looks like. A worker returns something plausible, the orchestrator accepts it without checking, and the assembled result is confidently wrong in a way no single call would have been. The synthesis step is where I have seen the most quiet failures.",
      "In a good one I look for a worker interface that is narrow and typed, so the orchestrator cannot hand over ambiguous work, and for the orchestrator's plan to be logged as a first-class artifact I can read afterwards. If I cannot see the plan, I cannot tell whether a bad result came from bad planning or bad execution.",
    ],
  },
  "evaluator-optimizer": {
    key: "evaluator-optimizer",
    name: "Evaluator-optimizer",
    oneLine:
      "One agent produces, another judges, and the loop runs until the judge is satisfied.",
    long: [
      "Evaluator-optimizer pairs two calls in a loop. One generates a response, the other evaluates it against clear criteria and returns feedback, and the generator tries again with that feedback in hand. The loop ends when the evaluator is satisfied or when a fixed number of rounds runs out.",
      "I reach for it when I can write down what good looks like well enough that a model can check for it, and when a first draft is reliably improved by specific criticism. Literary translation, where a reviewer can name the nuance the first pass missed, is the classic case. Search tasks that need several rounds of refining and re-checking are another.",
      "The cost is rounds. Each pass through the loop is two calls, and a loose evaluator can keep a generator circling for a long time while the output barely changes. I always cap the iterations and I always log every round, because the bill for this pattern arrives quietly.",
      "It goes wrong when the evaluator's criteria are vague. Asked whether something is good, a model will usually say it could be better, and the generator will dutifully change things that did not need changing. The other failure is the two roles collapsing into one voice, so the evaluator approves whatever the generator would have produced anyway.",
      "In a good one I look for evaluation criteria I could hand to a person, a feedback format that names specific problems rather than issuing grades, and evidence that the loop actually converges. If the third draft is not measurably better than the first on the stated criteria, the pattern is costing me money for nothing.",
    ],
  },
  "autonomous-agent": {
    key: "autonomous-agent",
    name: "Autonomous agent",
    oneLine:
      "A model in a loop with tools, deciding its own next step until the job is done.",
    long: [
      "An autonomous agent is a model in a loop. It takes a task from a person, plans, calls a tool, reads what came back, and decides what to do next, and it keeps doing that until it judges the job done or hits a stopping condition. The environment, through tool results, is what tells it whether it is making progress.",
      "I reach for it when the path through the task cannot be scripted and the number of steps is genuinely unknown. My digital twin is one. It answers questions about my career from a set of knowledge files loaded whole into its prompt, uses tools to record what it cannot answer, and knows when to stop and hand the conversation to me instead of guessing.",
      "The cost is trust and money. An agent that runs for twenty steps has twenty chances to compound a small mistake, and every step is a model call. It needs guardrails, a maximum number of iterations, and checkpoints where a human can look at what it has done so far before it goes further.",
      "It goes wrong when the tools are badly described or the stopping condition is soft. An agent with a vague tool will call it wrong and then reason its way around the failure instead of reporting it. An agent without a clear definition of done will either quit early or keep going long after the useful work ended.",
      "In a good one I look for tools that are documented as carefully as the prompt, a loop I can watch step by step in the logs, and an explicit hand-off path for when the agent is out of its depth. I would rather an agent say it does not know than produce something plausible I have to check anyway.",
    ],
  },
};

export const PATTERN_LIST: Pattern[] = PATTERN_KEYS.map((k) => PATTERNS[k]);
