import JDUploader from '../components/JDUploader';

export const metadata = {
  title: 'Upload Job Description — AI Recruiter',
  description: 'Decompose and match candidate profiles against target job qualifications',
};

export default function UploadJDPage() {
  return (
    <div className="container page-content">
      <div className="upload-page animate-fade-in">
        <h1>Create Target Shortlist</h1>
        <p className="subtitle">
          Paste your role description below. Our multi-stage retrieval engine will extract key qualifications, embed semantic requirements, and rank your candidate pool instantly.
        </p>

        <div className="glass-card" style={{ marginTop: '2rem' }}>
          <JDUploader />
        </div>
      </div>
    </div>
  );
}
