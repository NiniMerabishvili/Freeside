/** XP earned when completing a task — scales with cognitive load (1–10). */
export function taskXp(cognitiveLoadScore: number): number {
  return Math.max(1, cognitiveLoadScore) * 10;
}

export function effectiveTaskXp(task: { cognitive_load_score: number; xp_earned?: number | null }): number {
  if (typeof task.xp_earned === "number") return task.xp_earned;
  return taskXp(task.cognitive_load_score);
}
