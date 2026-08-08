import { Button, Input, Tooltip } from 'antd'
import { ArrowUpOutlined } from '@ant-design/icons'

const { TextArea } = Input

type ChatInputProps = {
  accentColor: string
  draft: string
  onDraftChange: (value: string) => void
  onSend: () => void
}

export function ChatInput({ accentColor, draft, onDraftChange, onSend }: ChatInputProps) {
  return (
    <div className="absolute bottom-4 left-4 right-4 z-20 mx-auto max-w-[980px]">
      <div className="relative rounded-2xl border border-slate-200 bg-white/90 p-2 shadow-lg backdrop-blur-md transition-all">
        <TextArea
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          onPressEnter={(event) => {
            if (event.shiftKey) return
            event.preventDefault()
            onSend()
          }}
          autoSize={{ minRows: 2, maxRows: 6 }}
          placeholder="Ask Travelmate to refine itinerary, budget, transport, and food..."
          className="border-none bg-transparent pr-12 text-[14px] focus:shadow-none focus:ring-0"
        />
        <Tooltip title="发送 (Enter)">
          <Button
            type="primary"
            shape="circle"
            icon={<ArrowUpOutlined />}
            onClick={onSend}
            className="absolute bottom-3 right-3 flex h-9 w-9 items-center justify-center border-0 shadow-md transition-transform active:scale-95"
            style={{ background: accentColor }}
          />
        </Tooltip>
      </div>
    </div>
  )
}
