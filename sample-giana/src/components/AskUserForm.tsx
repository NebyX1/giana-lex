import { useState, type FormEvent } from 'react'
import { Button, Card, Checkbox, Field, Input, Radio, RadioGroup, Text } from '@fluentui/react-components'
import type { PendingQuestion } from '../types'
import { useAppStyles } from '../styles'
import { AppIcon } from './AppIcon'

type Answer = string | string[] | boolean
type Props = { request: PendingQuestion; busy: boolean; onSubmit: (answers: Record<string, Answer>) => void }

export function AskUserForm({ request, busy, onSubmit }: Props) {
  const styles = useAppStyles()
  const [answers, setAnswers] = useState<Record<string, Answer>>({})

  function submit(event: FormEvent) {
    event.preventDefault()
    onSubmit(answers)
  }

  return <Card className={styles.questionCard}>
    <div className={styles.questionHeader}>
      <div className={styles.questionIcon}><AppIcon name="document" size={19} /></div>
      <div><Text weight="semibold" size={500}>Información necesaria</Text><Text className={styles.muted} block>Complete estos datos para continuar con el análisis.</Text></div>
      <Text className={styles.questionCount} size={200}>{request.questions.length} {request.questions.length === 1 ? 'campo' : 'campos'}</Text>
    </div>
    <form className={styles.formStack} onSubmit={submit}>
      {request.questions.map((question, index) => <div className={styles.questionField} key={question.id}><div className={styles.questionNumber}>{String(index + 1).padStart(2, '0')}</div><Field label={question.question} required={question.required}>
        {question.type === 'text' ? <Input required={question.required} value={(answers[question.id] as string) ?? ''} onChange={(_, data) => setAnswers({ ...answers, [question.id]: data.value })} /> : null}
        {question.type === 'single_choice' ? <RadioGroup required={question.required} value={(answers[question.id] as string) ?? ''} onChange={(_, data) => setAnswers({ ...answers, [question.id]: data.value })}>
          {question.options.map((option) => <Radio key={option} value={option} label={option} />)}
        </RadioGroup> : null}
        {question.type === 'multiple_choice' ? <div className={styles.choices}>{question.options.map((option) => {
          const selected = (answers[question.id] as string[] | undefined) ?? []
          return <Checkbox key={option} label={option} checked={selected.includes(option)} onChange={(_, data) => setAnswers({ ...answers, [question.id]: data.checked ? [...selected, option] : selected.filter((item) => item !== option) })} />
        })}</div> : null}
        {question.type === 'confirmation' ? <RadioGroup required={question.required} value={answers[question.id] === true ? 'yes' : answers[question.id] === false ? 'no' : ''} onChange={(_, data) => setAnswers({ ...answers, [question.id]: data.value === 'yes' })}>
          <Radio value="yes" label="Sí, confirmar" /><Radio value="no" label="No" />
        </RadioGroup> : null}
      </Field></div>)}
      <div className={styles.questionActions}><Text className={styles.muted} size={200}>Revise la información antes de continuar.</Text><Button appearance="primary" icon={<AppIcon name="send" />} iconPosition="after" type="submit" disabled={busy}>Continuar análisis</Button></div>
    </form>
  </Card>
}
