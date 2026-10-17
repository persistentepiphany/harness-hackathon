import { redirect } from 'next/navigation';

// The prototype starts on the "new" view (logic-v2.js: state.view = 'new').
export default function Home(): never {
  redirect('/runs/new');
}
