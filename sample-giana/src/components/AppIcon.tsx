type IconName =
  | 'attach'
  | 'arrow-left'
  | 'archive'
  | 'book'
  | 'building'
  | 'chat'
  | 'chevron'
  | 'document'
  | 'download'
  | 'collapse'
  | 'expand'
  | 'logout'
  | 'history'
  | 'more'
  | 'moon'
  | 'plus'
  | 'send'
  | 'search'
  | 'settings'
  | 'shield'
  | 'spark'
  | 'sources'
  | 'sun'
  | 'trash'
  | 'users'
  | 'restore'

const paths: Record<IconName, string> = {
  attach: 'M7.5 12.5 14.9 5a3 3 0 0 1 4.2 4.2l-9 9a5 5 0 0 1-7.1-7.1l8.3-8.3 1.4 1.4-8.3 8.3a3 3 0 0 0 4.3 4.3l9-9a1 1 0 1 0-1.4-1.4l-7.4 7.5a1 1 0 0 0 1.4 1.4l6.7-6.7 1.4 1.4-6.7 6.7a3 3 0 0 1-4.2-4.2Z',
  'arrow-left': 'M20 11v2H7.8l5.6 5.6L12 20l-8-8 8-8 1.4 1.4L7.8 11H20Z',
  archive: 'M4 3h16a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2v10H4V10a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm0 2v3h16V5H4Zm2 5v8h12v-8H6Zm3 2h6v2H9v-2Z',
  book: 'M4 3h13a3 3 0 0 1 3 3v13H6a3 3 0 0 1-3-3V4a1 1 0 0 1 1-1Zm2 2a1 1 0 0 0-1 1v7.2c.3-.1.7-.2 1-.2h12V6a1 1 0 0 0-1-1H6Zm0 10a1 1 0 0 0 0 2h12v-2H6Z',
  building: 'M4 21V8l8-5 8 5v13h-7v-5h-2v5H4Zm2-2h3v-5h6v5h3V9l-6-3.7L6 9v10Zm2-8h2v2H8v-2Zm6 0h2v2h-2v-2Z',
  chat: 'M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-5 4v-4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Zm0 2v10h2v1.8L8.4 16H20V6H4Z',
  chevron: 'm9 5 7 7-7 7-1.4-1.4 5.6-5.6-5.6-5.6L9 5Z',
  document: 'M6 2h8l5 5v15H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm7 2H6v16h11V8h-4V4Zm2 1.4V6h.6L15 5.4ZM8 11h7v2H8v-2Zm0 4h7v2H8v-2Z',
  download: 'M11 3h2v10.2l3.6-3.6L18 11l-6 6-6-6 1.4-1.4 3.6 3.6V3ZM4 19h16v2H4v-2Z',
  collapse: 'M9 3v6H3V7h4V3h2Zm6 0h2v4h4v2h-6V3ZM3 15h6v6H7v-4H3v-2Zm12 0h6v2h-4v4h-2v-6Z',
  expand: 'M3 3h6v2H5v4H3V3Zm12 0h6v6h-2V5h-4V3ZM3 15h2v4h4v2H3v-6Zm16 0h2v6h-6v-2h4v-4Z',
  logout: 'M10 3H4v18h6v-2H6V5h4V3Zm5.6 4.6L14.2 9l2 2H9v2h7.2l-2 2 1.4 1.4L20 12l-4.4-4.4Z',
  history: 'M12 3a9 9 0 1 1-8.5 6H1l3.5-4L8 9H5.6A7 7 0 1 0 12 5V3Zm-1 4h2v5.2l3.4 2-1 1.7L11 13.4V7Z',
  more: 'M5 10a2 2 0 1 1 0 4 2 2 0 0 1 0-4Zm7 0a2 2 0 1 1 0 4 2 2 0 0 1 0-4Zm7 0a2 2 0 1 1 0 4 2 2 0 0 1 0-4Z',
  moon: 'M20.5 15.3A8.5 8.5 0 0 1 8.7 3.5 9 9 0 1 0 20.5 15.3ZM12 20a7 7 0 0 1-5.2-11.7 10.5 10.5 0 0 0 8.9 8.9A7 7 0 0 1 12 20Z',
  plus: 'M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z',
  send: 'm3 3 19 9-19 9 3.5-8L16 12 6.5 11 3 3Zm4.8 9 1.3 3.1L16.2 12 9.1 8.9 7.8 12Z',
  search: 'M10.5 3a7.5 7.5 0 1 1-4.7 13.3L2.1 20 3.5 21.4l3.8-3.8A7.5 7.5 0 0 1 10.5 3Zm0 2a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11Z',
  settings: 'M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8Zm0 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm8.6 3.8 1.4 1-2 3.5-1.7-.7c-.5.4-1 .7-1.6.9l-.2 1.8h-4l-.2-1.8c-.6-.2-1.1-.5-1.6-.9l-1.7.7-2-3.5 1.4-1a7 7 0 0 1 0-1.8L7 11l2-3.5 1.7.7c.5-.4 1-.7 1.6-.9l.2-1.8h4l.2 1.8c.6.2 1.1.5 1.6.9l1.7-.7 2 3.5-1.4 1a7 7 0 0 1 0 1.8Z',
  shield: 'M12 2 4.5 5v6.2c0 5 3.1 9.4 7.5 11.2 4.4-1.8 7.5-6.2 7.5-11.2V5L12 2Zm0 2.2 5.5 2.2v4.8c0 3.8-2.2 7.3-5.5 9-3.3-1.7-5.5-5.2-5.5-9V6.4L12 4.2Zm-1.1 11.4-3-3 1.4-1.4 1.6 1.6 4-4 1.4 1.4-5.4 5.4Z',
  spark: 'm12 2 1.6 5.4L19 9l-5.4 1.6L12 16l-1.6-5.4L5 9l5.4-1.6L12 2Zm7 12 .9 3.1L23 18l-3.1.9L19 22l-.9-3.1L15 18l3.1-.9L19 14ZM5 13l1.1 3.9L10 18l-3.9 1.1L5 23l-1.1-3.9L0 18l3.9-1.1L5 13Z',
  sources: 'M5 3h14v4H5V3Zm0 7h14v4H5v-4Zm0 7h14v4H5v-4ZM7 5h10v0H7Zm0 7h10v0H7Zm0 7h10v0H7Z',
  sun: 'M12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10Zm0 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6Zm-1-8h2v4h-2V1Zm0 18h2v4h-2v-4ZM1 11h4v2H1v-2Zm18 0h4v2h-4v-2ZM4.2 2.8 7 5.6 5.6 7 2.8 4.2l1.4-1.4Zm14.2 14.2 2.8 2.8-1.4 1.4-2.8-2.8 1.4-1.4ZM19.8 2.8l1.4 1.4L18.4 7 17 5.6l2.8-2.8ZM5.6 17 7 18.4l-2.8 2.8-1.4-1.4L5.6 17Z',
  trash: 'M8 3h8l1 2h4v2H3V5h4l1-2Zm-2 6h12l-1 12H7L6 9Zm2.2 2 .7 8h6.2l.7-8H8.2Zm2.8 1h2v5h-2v-5Z',
  users: 'M9 3a4 4 0 1 1 0 8 4 4 0 0 1 0-8Zm0 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm7.5 2a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Zm0 2a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3ZM9 13c4.4 0 7 2.2 7 5v3H2v-3c0-2.8 2.6-5 7-5Zm0 2c-3.1 0-5 .12-5 3v1h10v-1c0-1.3-1.9-3-5-3Zm7.6.5c3.4 0 5.4 1.7 5.4 4V21h-4v-2h1.9c-.3-.7-1.5-1.5-3.3-1.5v-2Z',
  restore: 'M5.6 7H9v2H2V2h2v3.4A9 9 0 1 1 3.8 17l1.8-1a7 7 0 1 0 0-9Z',
}

export function AppIcon({ name, size = 18 }: { name: IconName; size?: number }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width={size} height={size} fill="currentColor"><path d={paths[name]} /></svg>
}
