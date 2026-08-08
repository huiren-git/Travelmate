import { itineraryImagePrompts } from '../assets/chatImagePrompts'
import type { ChatMessage, Conversation, ExpenseCategory, ItineraryItem, TripSummary } from '../types/chat'
import { img } from '../utils/image'

export const conversations: Conversation[] = [
  { id: 'c1', title: '北京三日游', updatedAt: '今天', status: '进行中' },
  { id: 'c2', title: '成都美食周末', updatedAt: '昨天', status: '已完成' },
  { id: 'c3', title: '上海亲子两日', updatedAt: '3天前', status: '已完成' },
  { id: 'c4', title: '西安历史路线', updatedAt: '上周', status: '已完成' },
]

export const initialMessages: ChatMessage[] = [
  {
    id: 'm1',
    role: 'assistant',
    content:
      '我已为「北京三日游」生成初版行程：包含经典景点、交通建议与预算拆分。你更偏好“文化历史”还是“Citywalk + 咖啡馆”？',
    time: '09:10',
  },
  { id: 'm2', role: 'user', content: '更偏文化历史，同时希望节奏别太赶。', time: '09:12' },
  {
    id: 'm3',
    role: 'assistant',
    content: '收到。我会基于步行距离与地铁换乘成本重新优化动线，并用预算上限做一次费用约束。你们有老人或小朋友吗？',
    time: '09:13',
  },
]

export const assistantReplyContent = '已收到。我会基于你的偏好更新行程，并把预算与时间安排同步到右侧计划面板。'

export const itinerary: ItineraryItem[] = [
  {
    id: 'i1',
    date: '2026.8.10',
    attractionName: '故宫博物院',
    timeRange: '09:00 - 12:00',
    priceCny: 60,
    status: '已确认',
    category: '景酒',
    imageUrl: img(itineraryImagePrompts.forbiddenCity, 'landscape_4_3'),
  },
  {
    id: 'i2',
    date: '2026.8.10',
    attractionName: '景山公园日落',
    timeRange: '16:30 - 18:30',
    priceCny: 2,
    status: '待确认',
    category: '景酒',
    imageUrl: img(itineraryImagePrompts.jingshanSunset, 'landscape_4_3'),
  },
  {
    id: 'i3',
    date: '2026.8.11',
    attractionName: '颐和园',
    timeRange: '10:00 - 14:00',
    priceCny: 40,
    status: '待确认',
    category: '景酒',
    imageUrl: img(itineraryImagePrompts.summerPalace, 'landscape_4_3'),
  },
  {
    id: 'i4',
    date: '2026.8.12',
    attractionName: '天坛公园',
    timeRange: '09:30 - 11:30',
    priceCny: 15,
    status: '已完成',
    category: '景酒',
    imageUrl: img(itineraryImagePrompts.templeOfHeaven, 'landscape_4_3'),
  },
]

export const trip: TripSummary = {
  title: '北京三日游',
  dateRange: '2026.8.10 - 2026.8.12',
  people: 3,
  budgetCny: 6000,
  spentCny: 2350,
}

export const expensesByCategory: ExpenseCategory[] = [
  { name: '景点/门票', amount: 117, color: '#0071EB' },
  { name: '餐饮/美食', amount: 1200, color: '#FF6F61' },
  { name: '交通/出行', amount: 433, color: '#10B981' },
  { name: '住宿/酒店', amount: 600, color: '#F59E0B' },
]
