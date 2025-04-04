import { Dispatch, SetStateAction, useCallback, useEffect, useState } from 'react';
import { Input } from '../ui/Input';

type GoogleConfigFormProps = {
  setConfig: Dispatch<SetStateAction<Record<string, unknown> | undefined>>;
};

export function GoogleConfigForm(props: GoogleConfigFormProps) {
  const { setConfig } = props;

  const [projectId, setProjectId] = useState<string>();
  const [location, setLocation] = useState<string>();
  const [credentials, setCredentials] = useState<string>();

  const onProjectIdChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setProjectId(e.target.value);
  }, []);

  const onLocationChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setLocation(e.target.value);
  }, []);

  const onCredentialsChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const data = reader.result as string;
      setCredentials(data);
    };
    reader.readAsDataURL(file);
  }, []);

  useEffect(() => {
    if (!projectId || !location || !credentials) {
      setConfig(undefined);
      return;
    }

    setConfig({
      vertex_project: projectId,
      vertex_location: location,
      vertex_credentials: credentials,
    });
  }, [projectId, location, credentials, setConfig]);

  return (
    <div className='flex flex-col items-start gap-6 w-full'>
      <div className='flex flex-col items-start gap-3 w-full max-w-[600px]'>
        <label htmlFor='project-id' className='text-[14px] text-slate-600 font-medium'>
          Project ID
        </label>
        <Input
          id='project-id'
          placeholder='The ID of your Google Vertex Project'
          onChange={onProjectIdChange}
          value={projectId}
          className='w-full rounded-[10px]'
        />
      </div>

      <div className='flex flex-col items-start gap-3 w-full max-w-[600px]'>
        <label htmlFor='location' className='text-[14px] text-slate-600 font-medium'>
          Location
        </label>
        <Input
          id='location'
          placeholder='The region of the project, eg. us-central1'
          onChange={onLocationChange}
          value={location}
          className='w-full rounded-[10px]'
        />
      </div>

      <div className='flex flex-col items-start gap-3 w-full max-w-[600px]'>
        <label htmlFor='credentials' className='text-[14px] text-slate-600 font-medium'>
          Credentials
        </label>
        <Input
          type='file'
          id='Credentials'
          placeholder='JSON file containing sign-in info'
          onChange={onCredentialsChange}
          className='w-full rounded-[10px]'
        />
      </div>
    </div>
  );
}
