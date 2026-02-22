export function buildPostUrl(postPath: string): string {
  let slug = postPath
  if (slug.startsWith('posts/')) {
    slug = slug.slice(6)
  }
  if (slug.endsWith('/index.md')) {
    slug = slug.slice(0, -9)
  } else if (slug.endsWith('.md')) {
    slug = slug.slice(0, -3)
  }
  return `${window.location.origin}/post/${slug}`
}

export function buildDefaultText(
  postTitle: string,
  postExcerpt: string,
  postLabels: string[],
  postPath: string,
): string {
  const excerpt = postExcerpt || postTitle
  const hashtags = postLabels
    .slice(0, 5)
    .map((label) => `#${label}`)
    .join(' ')
  const url = buildPostUrl(postPath)

  const parts = [excerpt]
  if (hashtags) {
    parts.push(hashtags)
  }
  parts.push(url)

  return parts.join('\n\n')
}
