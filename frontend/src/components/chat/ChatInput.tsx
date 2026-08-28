import { ArrowUpOutlined, UnorderedListOutlined } from '@ant-design/icons'
import { Badge, Button, Checkbox, Form, Input, InputNumber, Modal, Radio, Select, Tooltip } from 'antd'
import { useState } from 'react'
import type { StructuredPreferences } from '../../types/chat'
import { useI18n } from '../../i18n'

const { TextArea } = Input

type ChatInputProps = {
  accentColor: string
  draft: string
  onDraftChange: (value: string) => void
  onSend: () => void
  onStructuredPreferencesChange: (preferences: StructuredPreferences | undefined) => void
  structuredPreferences: StructuredPreferences | undefined
}

const budgetOptions: StructuredPreferences['budget_level'][] = ['经济实惠', '舒适出行', '奢华体验']
const paceOptions: NonNullable<StructuredPreferences['pace']>[] = ['轻松', '适中', '紧凑']
const interestOptions = ['美食', '摄影', '自然风光', '人文古迹', '亲子活动', '购物']
const travelerTypeOptions: NonNullable<StructuredPreferences['travelers_type']>[] = [
  '独自出行',
  '情侣',
  '亲子',
  '朋友',
  '家庭',
  '长辈同行',
]
const hotelOptions: NonNullable<StructuredPreferences['hotel_preference']>[] = [
  '经济型酒店',
  '舒适型酒店',
  '高端酒店',
  '特色民宿',
]
const intercityTransportOptions: NonNullable<StructuredPreferences['intercity_transport']>[] = ['火车', '飞机', '自驾', '无偏好']
const localTransportOptions: NonNullable<StructuredPreferences['local_transport']>[] = ['步行', '公共交通', '打车', '租车', '无偏好']

function normalizePreferences(values: StructuredPreferences): StructuredPreferences | undefined {
  const normalized = Object.fromEntries(
    Object.entries(values).filter(([, value]) => value !== undefined && (!Array.isArray(value) || value.length > 0)),
  ) as StructuredPreferences

  return Object.keys(normalized).length > 0 ? normalized : undefined
}

export function ChatInput({
  accentColor,
  draft,
  onDraftChange,
  onSend,
  onStructuredPreferencesChange,
  structuredPreferences,
}: ChatInputProps) {
  const [form] = Form.useForm<StructuredPreferences>()
  const [isPreferencesModalOpen, setIsPreferencesModalOpen] = useState(false)
  const hasStructuredPreferences = Boolean(structuredPreferences && Object.keys(structuredPreferences).length > 0)
  const { t } = useI18n()

  function openPreferencesModal() {
    form.setFieldsValue(structuredPreferences ?? {})
    setIsPreferencesModalOpen(true)
  }

  function savePreferences() {
    onStructuredPreferencesChange(normalizePreferences(form.getFieldsValue()))
    setIsPreferencesModalOpen(false)
  }

  return (
    <>
      <div className="absolute bottom-4 left-4 right-4 z-20 mx-auto max-w-[1000px]">
        <div className="relative rounded-2xl border border-slate-200 bg-white/90 pt-2 px-2 pb-2 shadow-lg backdrop-blur-md transition-all dark:border-slate-700 dark:bg-slate-800/90">
          <TextArea
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            onPressEnter={(event) => {
              if (event.shiftKey) return
              event.preventDefault()
              onSend()
            }}
            autoSize={{ minRows: 5, maxRows: 9 }}
            placeholder={t('chat.placeholder')}
            className="border-none bg-transparent pt-10 pb-10 pl-10 pr-14 text-[14px] text-slate-800 focus:shadow-none focus:ring-0 dark:text-slate-100"
          />
          <div className="absolute bottom-3 left-3">
            <Tooltip title={t('chat.planListTooltip')}>
              <Badge dot={hasStructuredPreferences} color={accentColor} offset={[-2, 2]}>
                <Button
                  type="text"
                  shape="circle"
                  icon={<UnorderedListOutlined />}
                  onClick={openPreferencesModal}
                  className="flex h-8 w-8 items-center justify-center text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-700 dark:hover:text-slate-100"
                />
              </Badge>
            </Tooltip>
          </div>
          <div className="absolute bottom-3 right-3">
            <Tooltip title={t('chat.sendTooltip')}>
              <Button
                type="primary"
                shape="circle"
                icon={<ArrowUpOutlined />}
                onClick={onSend}
                className="flex h-10 w-10 items-center justify-center border-0 shadow-md transition-transform active:scale-95"
                style={{ background: accentColor }}
              />
            </Tooltip>
          </div>
        </div>
      </div>

      <Modal
        centered
        destroyOnHidden
        open={isPreferencesModalOpen}
        title={t('chat.planListTitle')}
        okText={t('chat.savePreferences')}
        cancelText={t('settings.cancel')}
        onCancel={() => setIsPreferencesModalOpen(false)}
        onOk={savePreferences}
        width={680}
      >
        <Form form={form} layout="vertical" className="pt-2">
          <div className="grid gap-x-4 md:grid-cols-2">
            <Form.Item label={t('chat.startDate')} name="start_date">
              <Input type="date" className="w-full" />
            </Form.Item>
            <Form.Item label="出发城市" name="origin">
              <Input placeholder="例如：上海（不填则不计入城际交通）" />
            </Form.Item>

            <Form.Item label={t('chat.budgetLevel')} name="budget_level">
              <Radio.Group optionType="button" buttonStyle="solid">
                {budgetOptions.map((option) => (
                  <Radio.Button key={option} value={option}>
                    {t(`chat.opt.budget.${option}`)}
                  </Radio.Button>
                ))}
              </Radio.Group>
            </Form.Item>

            <Form.Item label={t('chat.pace')} name="pace">
              <Radio.Group optionType="button" buttonStyle="solid">
                {paceOptions.map((option) => (
                  <Radio.Button key={option} value={option}>
                    {t(`chat.opt.pace.${option}`)}
                  </Radio.Button>
                ))}
              </Radio.Group>
            </Form.Item>

            <Form.Item label={t('chat.travelers')} name="travelers">
              <InputNumber className="w-full" min={1} max={20} placeholder={t('chat.travelersPlaceholder')} />
            </Form.Item>

            <Form.Item label={t('chat.travelersType')} name="travelers_type">
              <Select
                allowClear
                placeholder={t('chat.travelersTypePlaceholder')}
                options={travelerTypeOptions.map((value) => ({ label: t(`chat.opt.travelersType.${value}`), value }))}
              />
            </Form.Item>

            <Form.Item label={t('chat.hotelPreference')} name="hotel_preference">
              <Select
                allowClear
                placeholder={t('chat.hotelPlaceholder')}
                options={hotelOptions.map((value) => ({ label: t(`chat.opt.hotel.${value}`), value }))}
              />
            </Form.Item>

            <Form.Item label={t('chat.intercityTransport')} name="intercity_transport">
              <Select
                allowClear
                placeholder={t('chat.intercityPlaceholder')}
                options={intercityTransportOptions.map((value) => ({ label: t(`chat.opt.intercity.${value}`), value }))}
              />
            </Form.Item>
            <Form.Item label="包含返程" name="include_return" valuePropName="checked" initialValue>
              <Checkbox>将返程城际交通计入预算</Checkbox>
            </Form.Item>

            <Form.Item label={t('chat.localTransport')} name="local_transport">
              <Select
                allowClear
                placeholder={t('chat.localPlaceholder')}
                options={localTransportOptions.map((value) => ({ label: t(`chat.opt.local.${value}`), value }))}
              />
            </Form.Item>
          </div>

          <Form.Item label={t('chat.interests')} name="interests">
            <Checkbox.Group
              options={interestOptions.map((value) => ({ label: t(`chat.opt.interest.${value}`), value }))}
              className="flex flex-wrap gap-x-4 gap-y-2"
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
