import { useState } from 'react'
import type { ItineraryCategory } from '../../types/chat'

type ItineraryImageProps = {
  src?: string | null
  alt?: string
  className?: string
  /**
   * 行程项类别，用于在缺图时选择语义更贴切的占位图：
   * 餐饮 → 餐具占位图；其余类别 → 风景占位图。
   * 未传时默认使用风景占位图。
   */
  category?: ItineraryCategory
}

/**
 * 餐具占位图：白色背景 + 居中的「刀子与勺子交叉成 X」SVG。
 * 仅用于餐饮类行程项缺图（image_url 为空）或图片加载失败时。
 */
export function CutleryPlaceholder({ className = '' }: { className?: string }) {
  return (
    <div
      className={`!flex items-center justify-center bg-white dark:bg-white ${className}`}
      aria-label="餐饮占位图"
      role="img"
    >
      <svg viewBox="0 0 1024 1024" className="h-[68px] w-[68px]" fill="#64748B" aria-hidden="true">
        <path d="M332.8 561.067l121.6-121.6L155.733 140.8c-66.133 66.133-66.133 174.933 0 241.067l177.067 179.2z m290.133-78.934c64 29.867 157.867 8.534 224-59.733C928 341.333 945.067 224 881.067 162.133 819.2 100.267 701.867 115.2 620.8 196.267c-68.267 68.266-89.6 160-59.733 224-93.867 96-416 418.133-416 418.133l59.733 59.733 294.4-294.4 294.4 294.4 59.733-59.733-294.4-292.267 64-64z" />
      </svg>
    </div>
  )
}

/**
 * 风景占位图：白色背景 + 居中的「山与太阳」SVG。
 * 用于非餐饮类（景酒/交通/娱乐/其他等）行程项缺图（image_url 为空）或图片加载失败时。
 */
export function SceneryPlaceholder({ className = '' }: { className?: string }) {
  return (
    <div
      className={`!flex items-center justify-center bg-white dark:bg-white ${className}`}
      aria-label="风景占位图"
      role="img"
    >
      <svg viewBox="0 0 1024 1024" className="h-[68px] w-[68px]" aria-hidden="true">
        <path
          fill="#464D70"
          d="M962.9696 835.2256H60.9792a30.72 30.72 0 1 0 0 61.44h901.9904a30.72 30.72 0 1 0 0-61.44zM145.4592 794.2656h735.488a63.6928 63.6928 0 0 0 57.2416-91.6992l-174.08-356.8128a63.744 63.744 0 0 0-105.8816-13.2608l-184.32 217.1904-50.7904-103.6288a55.552 55.552 0 0 0-92.16-11.5712l-227.8912 268.3392a55.552 55.552 0 0 0 42.3936 91.4432zM704.9216 372.224a2.0992 2.0992 0 0 1 2.048-0.768 1.9968 1.9968 0 0 1 1.7408 1.28l174.08 356.8128a1.9968 1.9968 0 0 1 0 2.2016 1.9968 1.9968 0 0 1-1.9456 1.0752H403.7632a1.9456 1.9456 0 0 1-2.048-1.3312 1.8944 1.8944 0 0 1 0.3072-2.4064l88.1152-103.8336zM371.8656 481.28L430.08 600.832l-74.8544 88.4736a52.4288 52.4288 0 0 0-3.3792 4.352c-0.3584 0.4608-0.6144 0.9216-0.9216 1.3824s-1.4848 2.2016-2.1504 3.328l-0.8192 1.4848a41.984 41.984 0 0 0-2.048 3.9936l-0.4096 0.768c-0.7168 1.6384-1.3824 3.2768-1.9456 5.12l-0.4608 1.3824c-0.4096 1.2288-0.768 2.5088-1.0752 3.7888 0 0.512-0.3072 1.0752-0.4096 1.5872-0.3072 1.3312-0.5632 2.7136-0.8192 4.0448v1.1776c0 1.7408-0.4096 3.4816-0.512 5.12a9.0624 9.0624 0 0 1 0 1.1776V732.928H158.1568z"
        />
        <path
          fill="#464D70"
          d="M476.16 378.4704a120.832 120.832 0 1 0-120.832-120.832A120.9856 120.9856 0 0 0 476.16 378.4704z m0-180.1728a59.392 59.392 0 1 1-59.392 59.3408A59.392 59.392 0 0 1 476.16 198.2976z"
        />
      </svg>
    </div>
  )
}

/**
 * 行程项图片：有图且加载成功时显示图片；否则（空 src 或加载失败）按类别显示占位图。
 * 餐饮类 → 餐具占位图；其余类别 → 风景占位图。
 */
export function ItineraryImage({ src, alt, className, category }: ItineraryImageProps) {
  const [failed, setFailed] = useState(false)

  if (!src || failed) {
    return category === '餐饮' ? (
      <CutleryPlaceholder className={className} />
    ) : (
      <SceneryPlaceholder className={className} />
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  )
}
