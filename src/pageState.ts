export const PageState = {
    Main: 'main',
    Questions: 'questions',
    Answer: 'answer',
} as const;

export type PageState = typeof PageState[keyof typeof PageState];