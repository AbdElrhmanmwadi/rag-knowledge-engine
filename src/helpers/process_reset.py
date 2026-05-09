async def reset_project_processing_state(chunk_model, vectordb_client, collection_name: str, project_id: str):
    await vectordb_client.delete_collection(collection_name=collection_name)
    await chunk_model.delete_chunks_by_project_id(project_id=project_id)