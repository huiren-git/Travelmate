import { TracesLayout } from '../layouts/TracesLayout'
import { useTracesPageData } from '../hooks/useTracesPageData'

export default function TracesPage() {
  const tracesPageData = useTracesPageData()

  return <TracesLayout {...tracesPageData} />
}
